#!/usr/bin/env python3

import json
import sqlite3
import sys
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any

from sklearn.metrics import ConfusionMatrixDisplay, classification_report

# Ensure the local ingredient_parser package can be found
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingredient_parser import SUPPORTED_LANGUAGES

sqlite3.register_converter("json", json.loads)


@dataclass
class DataVectors:
    """Dataclass to store the loaded and transformed inputs."""

    sentences: list[str]
    features: list[list[dict[str, str]]]
    tokens: list[list[str]]
    labels: list[list[str]]
    source: list[str]
    uids: list[int]


@dataclass
class Metrics:
    """Metrics returned by sklearn.metrics.classification_report for each label."""

    precision: float
    recall: float
    f1_score: float
    support: int


@dataclass
class TokenStats:
    """Statistics for token classification performance."""

    NAME: Metrics
    QTY: Metrics
    UNIT: Metrics
    SIZE: Metrics
    COMMENT: Metrics
    PURPOSE: Metrics
    PREP: Metrics
    PUNC: Metrics
    macro_avg: Metrics
    weighted_avg: Metrics
    accuracy: float


@dataclass
class FFTokenStats:
    """Statistics for token classification performance."""

    FF: Metrics
    NF: Metrics
    macro_avg: Metrics
    weighted_avg: Metrics
    accuracy: float


@dataclass
class SentenceStats:
    """Statistics for sentence classification performance."""

    accuracy: float


@dataclass
class Stats:
    """Statistics for token and sentence classification performance."""

    token: TokenStats
    sentence: SentenceStats
    seed: int


def select_preprocessor(lang: str) -> Any:
    """Select appropraite PreProcessor class for given language.

    Parameters
    ----------
    lang : str
        Language of training data

    Returns
    -------
    Any
        PreProcessor class for pre-processing in given language.

    Raises
    ------
    ValueError
        Selected langauage not supported
    """
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f'Unsupported language "{lang}"')

    match lang:
        case "en":
            from ingredient_parser.en import PreProcessor

            return PreProcessor


def load_datasets(
    database: str,
    table: str,
    datasets: list[str],
    foundation_foods: bool = False,
    discard_other: bool = True,
) -> DataVectors:
    """Load raw data from csv files and transform into format required for training.

    Parameters
    ----------
    database : str
        Path to database of training data
    table : str
        Name of database table containing training data
    datasets : list[str]
        List of data source to include.
        Valid options are: nyt, cookstr, bbc
    foundation_foods : bool, optional
        If True, prepare data for training foundation foods model.
        If False, load data for training parser model.
    discard_other : bool, optional
        If True, discard sentences containing tokens with OTHER label

    Returns
    -------
    DataVectors
        Dataclass holding:
            raw input sentences,
            features extracted from sentences,
            labels for sentences
            source dataset of sentences
    """
    print("[INFO] Loading and transforming training data.")

    with sqlite3.connect(database, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            f"SELECT * FROM {table} WHERE source IN ({','.join(['?']*len(datasets))})",
            datasets,
        )
        data = c.fetchall()
    conn.close()

    PreProcessor = select_preprocessor(table)

    source, sentences, features, tokens, labels, uids = [], [], [], [], [], []
    discarded = 0
    for entry in data:
        if discard_other and "OTHER" in entry["labels"]:
            discarded += 1
            continue

        source.append(entry["source"])
        sentences.append(entry["sentence"])
        p = PreProcessor(entry["sentence"])
        uids.append(entry["id"])

        if foundation_foods:
            name_idx = [idx for idx, lab in enumerate(entry["labels"]) if lab == "NAME"]
            name_labels = [
                "FF" if idx in entry["foundation_foods"] else "NF" for idx in name_idx
            ]
            name_features = [
                feat
                for idx, feat in enumerate(p.sentence_features())
                if idx in name_idx
            ]
            name_tokens = [
                token
                for idx, token in enumerate(p.tokenized_sentence)
                if idx in name_idx
            ]

            features.append(name_features)
            tokens.append(name_tokens)
            labels.append(name_labels)
        else:
            features.append(p.sentence_features())
            tokens.append(p.tokenized_sentence)
            labels.append(entry["labels"])

        # Ensure length of tokens and length of labels are the same
        if len(p.tokenized_sentence) != len(entry["labels"]):
            raise ValueError(
                (
                    f"\"{entry['sentence']}\" (ID: {entry['id']}) has "
                    f"{len(p.tokenized_sentence)} tokens "
                    f"but {len(entry['labels'])} labels."
                )
            )

    print(f"[INFO] {len(sentences):,} usable vectors.")
    print(f"[INFO] {discarded:,} discarded due to OTHER labels.")
    return DataVectors(sentences, features, tokens, labels, source, uids)


def evaluate(
    predictions: list[list[str]],
    truths: list[list[str]],
    seed: int,
    foundation_foods: bool = False,
) -> Stats:
    """Calculate statistics on the predicted labels for the test data.

    Parameters
    ----------
    predictions : list[list[str]]
        Predicted labels for each test sentence
    truths : list[list[str]]
        True labels for each test sentence
    seed : int
        Seed value that produced the results
    foundation_foods : bool, optional
        If True, generate stats for foundation foods model.
        If False, generate stats for parser model.

    Returns
    -------
    Stats
        Dataclass holding token and sentence statistics:
    """
    # Generate token statistics
    # Flatten prediction and truth lists
    flat_predictions = list(chain.from_iterable(predictions))
    flat_truths = list(chain.from_iterable(truths))
    labels = list(set(flat_predictions))

    report = classification_report(
        flat_truths,
        flat_predictions,
        labels=labels,
        output_dict=True,
    )

    # Convert report to TokenStats dataclass
    token_stats = {}
    for k, v in report.items():  # type: ignore
        # Convert dict to Metrics
        if k in labels + ["macro avg", "weighted avg"]:
            k = k.replace(" ", "_")
            token_stats[k] = Metrics(
                v["precision"], v["recall"], v["f1-score"], int(v["support"])
            )
        else:
            token_stats[k] = v

    if foundation_foods:
        token_stats = FFTokenStats(**token_stats)
    else:
        token_stats = TokenStats(**token_stats)

    # Generate sentence statistics
    # The only statistics that makes sense here is accuracy because there are only
    # true-positive results (i.e. correct) and false-negative results (i.e. incorrect)
    correct_sentences = len([p for p, t in zip(predictions, truths) if p == t])
    sentence_stats = SentenceStats(correct_sentences / len(predictions))

    return Stats(token_stats, sentence_stats, seed)


def confusion_matrix(
    predictions: list[list[str]],
    truths: list[list[str]],
    figure_path="confusion_matrix.svg",
) -> None:
    """Plot and save a confusion matrix for token labels.

    Parameters
    ----------
    predictions : list[list[str]]
        Predicted labels for each test sentence
    truths : list[list[str]]
        True labels for each test sentence
    figure_path : str, optional
        Path to save figure to.
    """
    # Flatten prediction and truth lists
    flat_predictions = list(chain.from_iterable(predictions))
    flat_truths = list(chain.from_iterable(truths))
    labels = list(set(flat_predictions))
    display_labels = [lab[:4] for lab in labels]

    cm = ConfusionMatrixDisplay.from_predictions(
        flat_truths, flat_predictions, labels=labels, display_labels=display_labels
    )
    cm.figure_.savefig(figure_path)
    print(f"[INFO] Confusion matrix saved to {figure_path}")
