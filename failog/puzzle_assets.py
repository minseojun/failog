# failog/puzzle_assets.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnimalAsset:
    key: str
    label: str
    path: Path


def animals_dir() -> Path:
    # failog/ 패키지 안의 assets/animals/ 를 기준으로 잡음
    # (너가 말한 "assets에 업로드" 구조가 failog/assets/animals 라는 가정)
    return Path(__file__).resolve().parent / "assets" / "animals"


def get_animal_assets() -> list[AnimalAsset]:
    d = animals_dir()

    # 너가 업로드한 파일명에 맞춰 여기만 수정하면 됨.
    # (파일 확장자 jpg/png 상관없음)
    candidates = [
        ("guinea_pig", "guinea", d / "guinea1.jpeg"),
        ("puppy", "puppy", d / "puppy1.jpeg"),
        ("bunny", "bunny", d / "bunny1.jpeg"),
        ("seal", "seal", d / "seal1.jpeg"),
    ]

    assets: list[AnimalAsset] = []
    for key, label, p in candidates:
        if p.exists():
            assets.append(AnimalAsset(key=key, label=label, path=p))

    # 업로드 파일명이 다르면 candidates의 파일명만 네 실제 파일명으로 맞춰줘.
    return assets
