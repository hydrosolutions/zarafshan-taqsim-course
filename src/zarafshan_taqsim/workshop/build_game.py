"""Assemble the offline Zarafshan trade-off game into one self-contained HTML file.

Usage: uv run python -m zarafshan_taqsim.workshop.build_game   (also rewrites key_numbers.json)

The page is built from workshop/zarafshan_game/game/{template.html,style.css,model.js,app.js} and the exported
zarafshan_game_data.json (written by `zarafshan_game.export_game_data`). Reference cases stay out of the page; the
pre-computed fronts are reduced to the indicators the explorer shows and rounded to keep the file small.
"""

import json
import logging
import math
from dataclasses import asdict, replace
from pathlib import Path

from zarafshan_taqsim.workshop.zarafshan_game import (
    AXES,
    CARDS,
    DAYS,
    HISTORICAL_PLAN,
    INFLOW_M3S,
    MEMBER_INDICATORS,
    YEARS,
    Levers,
    Settings,
    drainage_store_change,
    evaluate,
    volume,
)

logger = logging.getLogger(__name__)

GAME_DIR = Path(__file__).resolve().parents[3] / "workshop" / "zarafshan_game"
DATA_FILE = GAME_DIR / "zarafshan_game_data.json"
OUTPUT_FILE = GAME_DIR / "zarafshan_tradeoff_game.html"
KEY_NUMBERS_FILE = GAME_DIR / "key_numbers.json"

# Indicators carried into the page for every front member and year (the JS twin recomputes monthly series on demand).
FRONT_INDICATORS = tuple(k for k in MEMBER_INDICATORS if k != "balance_error")
# Page-size budget: eight fronts of up to 300 plans, each with FRONT_INDICATORS for three years, plus the scripts.
PAGE_SIZE_BUDGET_BYTES = 3 * 1024 * 1024


def _script_safe(source: str) -> str:
    return source.replace("</", "<\\/")


def _round(value: float, digits: int = 4) -> float:
    if value == 0 or not math.isfinite(value):
        return value
    return round(value, digits)


def _rounded(value: object) -> object:
    if isinstance(value, float):
        return _round(value)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(v) for v in value]
    return value


def page_data(data: dict) -> dict:
    """Only what the browser needs: constants, metadata, the reduced fronts and the analysis block."""
    fronts = {}
    for name, front in data["fronts"].items():
        fronts[name] = {
            "cards": front["cards"],
            "year": front["year"],
            "wall_time_s": front["wall_time_s"],
            "optimiser_members": front.get("optimiser_members", len(front["members"])),
            "members": [
                {
                    "levers": {k: _round(v) for k, v in member["levers"].items()},
                    "indicators": {
                        year: {k: _round(ind[k]) for k in FRONT_INDICATORS}
                        for year, ind in member["indicators"].items()
                    },
                }
                for member in front["members"]
            ],
        }
    return {
        "meta": data["meta"],
        "constants": data["constants"],
        "fronts": fronts,
        "analysis": _rounded(data.get("analysis", {})),
    }


def build_game(game_dir: Path = GAME_DIR, data_file: Path = DATA_FILE, output_file: Path = OUTPUT_FILE) -> Path:
    """Inline styles, data and scripts into a single HTML file that works without a network."""
    source = game_dir / "game"
    data = json.loads(data_file.read_text())
    parts = {
        "/*__STYLE__*/": (source / "style.css").read_text(),
        "/*__DATA__*/": _script_safe(json.dumps(page_data(data), separators=(",", ":"))),
        "/*__MODEL__*/": _script_safe((source / "model.js").read_text()),
        "/*__APP__*/": _script_safe((source / "app.js").read_text()),
    }
    page = (source / "template.html").read_text()
    for placeholder, content in parts.items():
        if page.count(placeholder) != 1:
            raise ValueError(f"template must contain {placeholder} exactly once")
        page = page.replace(placeholder, content)
    output_file.write_text(page)
    logger.info("wrote %s (%.0f kB)", output_file, output_file.stat().st_size / 1024)
    return output_file


# Headline indicators of the starting plan before the audit round (read: `git show 0bad1dd:workshop/zarafshan_game/
# key_numbers.json`, sections baseline_by_year and dry_year_tradeoff_F1), kept for the old-versus-new comparison.
PRE_AUDIT_HEADLINES: dict[str, dict[str, float]] = {
    "dry": {
        "irrigation_supply": 79.4,
        "irrigation_upstream": 99.7,
        "irrigation_tail": 55.6,
        "transfer_delivery": 100.0,
        "tpp_months": 10,
        "eflow_months": 8,
        "end_storage": 46.2,
        "outflow": 758.3,
    },
    "median": {
        "irrigation_supply": 88.3,
        "irrigation_upstream": 100.0,
        "irrigation_tail": 74.5,
        "transfer_delivery": 100.0,
        "tpp_months": 12,
        "eflow_months": 9,
        "end_storage": 46.2,
        "outflow": 1568.8,
    },
    "wet": {
        "irrigation_supply": 94.9,
        "irrigation_upstream": 100.0,
        "irrigation_tail": 88.9,
        "transfer_delivery": 100.0,
        "tpp_months": 12,
        "eflow_months": 11,
        "end_storage": 57.9,
        "outflow": 2371.1,
    },
}
PRE_AUDIT_ENVELOPE = {
    "start_storage": 333.5,
    "max_A1_with_A4_eq_12_and_transfers_ge_90": 78.8,
    "max_A4_with_A1_ge_85_and_transfers_ge_90": 6.0,
}
HEADLINE_KEYS = tuple(PRE_AUDIT_HEADLINES["dry"])
KEY_INDICATORS = (
    *FRONT_INDICATORS,
    "storage_initial",
    "municipal_shortfall",
    "conveyance_loss",
    "field_loss",
    "drainage_return",
    "evaporation",
    "fill",
    "fill_refused",
    "release",
    "consumed",
    "tpp_consumed",
    "equity",
    "balance_error",
)


def _indicators(settings: Settings, cards: tuple[str, ...], year: str, levers: Levers) -> dict[str, float]:
    indicators = evaluate(settings, cards, year, levers).indicators
    out = {k: round(indicators[k], 3) for k in KEY_INDICATORS}
    out["drainage_store_start"] = round(indicators["drainage_store_start"], 3)
    out["drainage_store_change"] = round(drainage_store_change(indicators), 3)
    return out


def key_numbers(data: dict, html_size_bytes: int | None = None) -> dict:
    """Every number the workshop documents quote, recomputed from the model and the exported data."""
    settings, start = Settings(), Levers()
    baseline = {y: _indicators(settings, (), y, start) for y in YEARS}
    dry = evaluate(settings, (), "dry", start)
    cards_alone = {card: _indicators(settings, (card,), "dry", start) for card in CARDS}
    delta_keys = ("irrigation_supply", "tpp_months", "eflow_months", "end_storage", "outflow", "drainage_return")
    probes = {
        "L1_canal_supply_0.5": replace(start, canal_supply=0.5),
        "L2_transfers_0": replace(start, transfer_share=0.0),
        "L3_fill_0.8": replace(start, fill_share=0.8),
        "L4_release_0": replace(start, release_share=0.0),
        "L5_plant_after_the_reserve": replace(start, tpp_priority=0.0),
        "L6_reserve_0": replace(start, reserve_share=0.0),
        "L6_reserve_0.3": replace(start, reserve_share=0.3),
        "past_operations_comparison_plan": HISTORICAL_PLAN,
    }
    setting_probes = {
        "start_storage_115": replace(settings, start_storage=115.0),
        "start_storage_340": replace(settings, start_storage=340.0),
        "drainage_share_0.2": replace(settings, drainage_share=0.2),
        "evaporation_scale_1.0_pan_series": replace(settings, evaporation_scale=1.0),
        "tpp_consumptive_1": replace(settings, tpp_consumptive_m3s=1.0),
    }
    analysis = data["analysis"]
    fronts = {}
    for name, front in data["fronts"].items():
        rows = [member["indicators"][front["year"]] for member in front["members"]]
        fronts[name] = {
            "cards": front["cards"],
            "year": front["year"],
            "displayed_members": len(rows),
            "optimiser_members": front["optimiser_members"],
            "wall_time_s": front["wall_time_s"],
            "range": {a: [round(min(r[a] for r in rows), 1), round(max(r[a] for r in rows), 1)] for a in AXES},
        }
    return {
        "_provenance": (
            "measured: `uv run python -m zarafshan_taqsim.workshop.build_game` (build_game.key_numbers) calling "
            "zarafshan_game.evaluate (TaqSim 0.1.4, 12 monthly steps) and reading zarafshan_game_data.json "
            "(export_game_data: NSGA-II fronts, a 20 000-plan Latin-hypercube dense search per pool, seed 7); "
            "every number is rounded output of those commands. `pre_audit` values are read from "
            "`git show 0bad1dd:workshop/zarafshan_game/key_numbers.json`."
        ),
        "starting_plan": asdict(start),
        "default_settings": asdict(settings),
        "optimiser": data["meta"]["optimiser"],
        "inflow_mm3_per_year": {
            y: round(sum(volume(q, d) for q, d in zip(INFLOW_M3S[y], DAYS, strict=True)), 1) for y in YEARS
        },
        "baseline_by_year": baseline,
        "old_vs_new_headline": {
            y: {k: {"pre_audit": PRE_AUDIT_HEADLINES[y][k], "now": round(baseline[y][k], 1)} for k in HEADLINE_KEYS}
            for y in YEARS
        },
        "pre_audit_envelope_F1": PRE_AUDIT_ENVELOPE,
        "baseline_dry_outflow_m3s_oct_to_sep": [round(v, 1) for v in dry.monthly["outflow_m3s"]],
        "baseline_dry_eflow_target_mm3_oct_to_sep": [round(v, 1) for v in dry.monthly["eflow_target"]],
        "baseline_dry_eflow_short_mm3_oct_to_sep": [round(v, 1) for v in dry.monthly["eflow_short"]],
        "baseline_dry_command_area_delivery_mm3_oct_to_sep": [
            round(v, 1) for v in dry.monthly["delivered_kattakurgan_irrigation"]
        ],
        "baseline_dry_storage_mm3_oct_to_sep": [round(v, 1) for v in dry.monthly["storage"]],
        "card_alone_dry_year": cards_alone,
        "card_alone_dry_year_delta_vs_baseline": {
            card: {k: round(values[k] - baseline["dry"][k], 3) for k in delta_keys}
            for card, values in cards_alone.items()
        },
        "lever_probes_dry_year": {name: _indicators(settings, (), "dry", levers) for name, levers in probes.items()},
        "settings_probes_dry_year": {name: _indicators(s, (), "dry", start) for name, s in setting_probes.items()},
        "fronts": fronts,
        "tradeoff_envelope": _rounded_to(analysis["envelope"], 1),
        "dense_search": analysis["dense"],
        "front_coverage": _rounded_to(analysis["coverage"], 3),
        "role_targets": analysis["role_targets"],
        "plant_priority_L5": _rounded_to(analysis["plant_priority"], 2),
        "card_effects_by_year": _rounded_to(analysis["cards"], 1),
        "drainage_stores": _rounded_to(analysis["drainage_stores"], 1),
        "navoi_comparison": _rounded_to(analysis["navoi"], 1),
        "storage_cycle": _rounded_to(analysis["storage_cycle"], 0),
        "html_size_bytes": html_size_bytes,
    }


def _rounded_to(value: object, digits: int) -> object:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: _rounded_to(v, digits) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded_to(v, digits) for v in value]
    return value


def write_key_numbers(data_file: Path = DATA_FILE, page: Path = OUTPUT_FILE, output: Path = KEY_NUMBERS_FILE) -> Path:
    data = json.loads(data_file.read_text())
    numbers = key_numbers(data, html_size_bytes=page.stat().st_size if page.exists() else None)
    output.write_text(json.dumps(numbers, indent=1, ensure_ascii=False) + "\n")
    logger.info("wrote %s", output)
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    build_game()
    write_key_numbers()
