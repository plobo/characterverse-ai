"""Deterministic local text 'LLM'. Produces structured data only (never code or Blender scripts, §7.2).

It stands in for a hosted/local LLM so that the full product works offline and in CI without paid APIs.
Output always flows through schema + registry validation, exactly like a real model's output would.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.ai.providers import ProviderInfo, stable_int

CATEGORY_WORDS = {
    "robot": "robot",
    "android": "robot",
    "mech": "robot",
    "bot": "robot",
    "cyborg": "robot",
    "villain": "villain",
    "evil": "villain",
    "sinister": "villain",
    "nemesis": "villain",
    "alien": "alien",
    "martian": "alien",
    "extraterrestrial": "alien",
    "space": "alien",
    "dragon": "creature",
    "beast": "creature",
    "monster": "creature",
    "creature": "creature",
    "wolf": "creature",
    "cartoon": "cartoon",
    "cute": "cartoon",
    "silly": "cartoon",
    "bunny": "cartoon",
    "critter": "cartoon",
    "wizard": "fantasy",
    "elf": "fantasy",
    "fairy": "fantasy",
    "magic": "fantasy",
    "druid": "fantasy",
    "hero": "hero",
    "guardian": "hero",
    "champion": "hero",
    "defender": "hero",
}
BASE_BY_CATEGORY = {
    "hero": "humanoid_base_01",
    "villain": "humanoid_toon_02",
    "cartoon": "critter_base_01",
    "fantasy": "humanoid_base_01",
    "robot": "mech_base_01",
    "alien": "alien_base_01",
    "creature": "creature_base_01",
}
STYLE_BY_CATEGORY = {
    "hero": "stylized_cinematic",
    "villain": "clay_matte",
    "cartoon": "toon_soft",
    "fantasy": "stylized_cinematic",
    "robot": "neon_lowpoly",
    "alien": "toon_soft",
    "creature": "stylized_cinematic",
}
COLOR_WORDS = {
    "blue": "#2F6FDE",
    "navy": "#1F2E5C",
    "green": "#3FA34D",
    "emerald": "#1F8A5B",
    "red": "#D7263D",
    "crimson": "#A4161A",
    "purple": "#6A3FB5",
    "violet": "#7B4FE0",
    "gold": "#E8B10C",
    "yellow": "#F4D35E",
    "silver": "#B8C0CC",
    "pink": "#F27CB2",
    "orange": "#F28C28",
    "black": "#22223B",
    "white": "#F4F4F8",
    "teal": "#1FA5A1",
    "brown": "#8C5A3C",
    "mint": "#9EE6CF",
}
POWER_WORDS = {
    "lightning": "electricity",
    "electric": "electricity",
    "thunder": "electricity",
    "spark": "electricity",
    "plant": "plant_growth",
    "leaf": "plant_growth",
    "forest": "plant_growth",
    "vine": "plant_growth",
    "fly": "flight",
    "flying": "flight",
    "wing": "flight",
    "soar": "flight",
    "ice": "ice",
    "frost": "ice",
    "snow": "ice",
    "freeze": "ice",
    "fire": "fire_breath",
    "flame": "fire_breath",
    "strong": "super_strength",
    "strength": "super_strength",
    "invisible": "invisibility",
    "stealth": "invisibility",
    "shapeshift": "shape_shift",
    "shift": "shape_shift",
    "shield": "force_field",
    "barrier": "force_field",
    "time": "time_slow",
    "roar": "sonic_roar",
    "gadget": "gadgetry",
    "tech": "gadgetry",
    "inventor": "gadgetry",
}
MODULE_WORDS = {
    "cape": "leaf_cape_01",
    "cloak": "leaf_cape_01",
    "horn": "crystal_horns_01",
    "horns": "crystal_horns_01",
    "wings": "moth_wings_01",
    "jetpack": "jet_pack_01",
    "jet": "jet_pack_01",
    "visor": "star_visor_01",
    "goggles": "star_visor_01",
    "antenna": "antenna_pair_01",
    "antennae": "antenna_pair_01",
    "armor": "original_armor_shoulders_02",
    "armour": "original_armor_shoulders_02",
    "bracers": "energy_bracers_03",
    "gauntlets": "energy_bracers_03",
    "scarf": "explorer_scarf_01",
    "tail": "spike_tail_01",
    "boots": "tread_boots_01",
}
SYLLABLES = ["zor", "vel", "mi", "ka", "thra", "lu", "nex", "bo", "ri", "qua", "fen", "do", "sa", "lyx", "tor", "pim"]
TITLES = {
    "hero": "Guardian",
    "villain": "Schemer",
    "cartoon": "Pip",
    "fantasy": "Mystic",
    "robot": "Unit",
    "alien": "Voyager",
    "creature": "Beast",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


class MockTextProvider:
    info = ProviderInfo(
        name="cv-local-structured-mock",
        version="1.0",
        kind="text",
        terms_url=None,
        cost_per_call_usd=0.0,
        typical_latency_ms=5,
        local=True,
    )

    # ------------------------------------------------------------------ characters
    def character_recipe(self, description: str, hints: dict[str, Any], vocab: dict[str, Any]) -> dict[str, Any]:
        words = _words(description)
        seed = stable_int(description)
        category = hints.get("category")
        if not category:
            category = next((CATEGORY_WORDS[w] for w in words if w in CATEGORY_WORDS), "hero")
        base = hints.get("baseModelId") or BASE_BY_CATEGORY[category]
        colors = [COLOR_WORDS[w] for w in words if w in COLOR_WORDS]
        defaults = ["#5B5FC7", "#2EC4B6", "#FFBF69", "#E71D36", "#7BDFF2", "#B2F7EF"]
        while len(colors) < 3:
            colors.append(defaults[(seed + len(colors)) % len(defaults)])
        powers: list[str] = []
        for w in words:
            p = POWER_WORDS.get(w) or POWER_WORDS.get(w.rstrip("s"))
            if p and p not in powers:
                powers.append(p)
        modules: list[str] = []
        for w in words:
            m = MODULE_WORDS.get(w)
            if m and m not in modules:
                modules.append(m)
        traits = [w for w in words if w in vocab["personalityTraits"]]
        traits = list(dict.fromkeys(traits))[:5] or [vocab["personalityTraits"][seed % len(vocab["personalityTraits"])]]
        name = hints.get("name") or self._name(seed, category)
        tall = (
            1.15
            if {"tall", "towering", "giant"} & set(words)
            else 0.88
            if {"small", "tiny", "little"} & set(words)
            else 1.0
        )
        broad = 1.18 if {"broad", "muscular", "bulky", "strong"} & set(words) else 1.0
        head = 1.2 if {"cute", "chibi", "bighead"} & set(words) else 1.0
        voices = vocab["voiceProfiles"]
        return {
            "schemaVersion": 1,
            "name": name,
            "category": category,
            "baseModelId": base,
            "style": hints.get("style") or STYLE_BY_CATEGORY[category],
            "proportions": {"height": tall, "shoulderWidth": broad, "headScale": head},
            "palette": {"primary": colors[0], "secondary": colors[1], "accent": colors[2]},
            "modules": modules,
            "powers": powers,
            "personalityTraits": traits,
            "voiceProfileId": voices[seed % len(voices)],
            "assetManifestVersion": vocab["manifestVersion"],
        }

    def _name(self, seed: int, category: str) -> str:
        a = SYLLABLES[seed % len(SYLLABLES)]
        b = SYLLABLES[(seed // 7) % len(SYLLABLES)]
        return f"{(a + b).capitalize()} {TITLES[category]}"

    def fusion_suggestions(self, names: list[str], traits: list[str]) -> list[dict[str, str]]:
        seed = stable_int(*names)
        firsts = [n.split()[0] for n in names]
        lasts = [n.split()[-1] for n in names]
        options = [
            f"{firsts[0][: max(3, len(firsts[0]) // 2 + 1)]}{firsts[1][len(firsts[1]) // 2 :].lower()}",
            f"{firsts[-1]} {lasts[0]}",
            f"{lasts[0]}-{lasts[-1]}",
        ]
        trait = traits[seed % len(traits)] if traits else "curious"
        return [{"name": o[:40], "tagline": f"A {trait} hybrid of {' and '.join(names)}."} for o in options]

    # ------------------------------------------------------------------ stories
    def storyboard(self, request: dict[str, Any], vocab: dict[str, Any]) -> dict[str, Any]:
        prompt: str = request.get("prompt") or ""
        chars: list[dict[str, Any]] = request["characters"]
        duration = request.get("durationSeconds", 30)
        tone = request.get("tone") or "uplifting"
        words = set(_words(prompt))
        seed = stable_int(prompt, *(c["characterId"] for c in chars))
        env_keywords = [
            ({"forest", "tree", "crystal", "woods", "jungle"}, "env_crystal_forest_01"),
            ({"moon", "space", "star", "planet", "galaxy"}, "env_moon_base_01"),
            ({"city", "sky", "tower", "harbor"}, "env_sky_city_01"),
            ({"village", "farm", "home", "cozy", "market"}, "env_cozy_village_01"),
            ({"neon", "night", "alley", "arcade"}, "env_neon_alley_01"),
        ]
        envs = [e for e in vocab["environments"]]
        primary_env = next((env for keys, env in env_keywords if keys & words), envs[seed % len(envs)])
        scene_count = {15: 3, 30: 4, 60: 6}[duration]
        per_scene = duration * 1000 // scene_count
        beats = ["intro", "problem", "action", "resolution", "twist", "finale"][:scene_count]
        if scene_count == 3:
            beats = ["intro", "action", "resolution"]
        elif scene_count == 4:
            beats = ["intro", "problem", "action", "resolution"]
        beat_actions = {
            "intro": ["wave", "idle", "talk"],
            "problem": ["point", "talk", "listen"],
            "action": ["action_combo_01", "run", "jump", "fly", "creature_prowl"],
            "twist": ["hit_react", "fall", "get_up"],
            "resolution": ["victory", "laugh", "dance_loop_01"],
            "finale": ["dance_loop_01", "victory", "clap"],
        }
        beat_camera = {
            "intro": "cam_wide",
            "problem": "cam_medium",
            "action": "cam_low_hero",
            "twist": "cam_closeup",
            "resolution": "cam_orbit",
            "finale": "cam_wide",
        }
        beat_sfx = {
            "intro": ["sfx_chime_01"],
            "problem": ["sfx_pop_01"],
            "action": ["sfx_whoosh_01", "sfx_zap_01"],
            "twist": ["sfx_thud_01"],
            "resolution": ["sfx_chime_01"],
            "finale": ["sfx_pop_01"],
        }
        music = {
            "playful": "music_adventure_loop_01",
            "uplifting": "music_adventure_loop_01",
            "heartwarming": "music_calm_meadow_01",
            "calm": "music_calm_meadow_01",
            "mysterious": "music_mystery_pulse_01",
            "spooky": "music_mystery_pulse_01",
        }.get(tone, "music_adventure_loop_01")
        lighting = (
            "light_night_neon"
            if primary_env in ("env_neon_alley_01", "env_moon_base_01")
            else ("light_sunset" if tone in ("heartwarming", "calm") else "light_daylight")
        )
        positions = {
            1: ["center"],
            2: ["left", "right"],
            3: ["left", "center", "right"],
            4: ["far_left", "left", "right", "far_right"],
        }[len(chars)]
        goal = self._goal(prompt)
        lead = chars[0]
        friend = chars[1] if len(chars) > 1 else chars[0]

        def line(beat: str, c: dict[str, Any], other: dict[str, Any]) -> str:
            trait = (c.get("traits") or ["brave"])[0]
            power = (c.get("powers") or ["courage"])[0].replace("_", " ")
            options = {
                "intro": f"Hi, I'm {c['displayName']}! Today we {goal}.",
                "problem": f"{other['displayName']}, something is wrong. We need a plan!",
                "action": f"Stand back - time for some {power}!",
                "twist": "Whoa! That did not go as planned.",
                "resolution": f"We did it! Being {trait} really paid off.",
                "finale": f"Same time tomorrow, {other['displayName']}?",
            }
            return options[beat][:140]

        scenes = []
        for i, beat in enumerate(beats):
            env = primary_env if i in (0, len(beats) - 1) else envs[(seed + i) % len(envs)]
            scene_chars = []
            for j, c in enumerate(chars):
                clips = [a for a in beat_actions[beat] if c["rig"] in vocab["clipRigs"].get(a, [])]
                scene_chars.append(
                    {
                        "characterId": c["characterId"],
                        "position": positions[j],
                        "scale": 1.0,
                        "actionId": clips[(seed + j) % len(clips)] if clips else "idle",
                    }
                )
            speaker = chars[i % len(chars)]
            other = friend if speaker is lead else lead
            dialogue = [{"characterId": speaker["characterId"], "line": line(beat, speaker, other), "startMs": 400}]
            if len(chars) > 1 and per_scene >= 5000:
                reply = "Right behind you!" if beat != "resolution" else "Best team in the universe!"
                dialogue.append({"characterId": other["characterId"], "line": reply, "startMs": per_scene // 2})
            scenes.append(
                {
                    "sceneId": f"scene_{i + 1}",
                    "sequence": i + 1,
                    "title": beat.capitalize(),
                    "description": f"{beat.capitalize()}: {lead['displayName']} and friends {goal}.",
                    "durationMs": per_scene,
                    "environmentId": env,
                    "cameraPresetId": beat_camera[beat],
                    "lightingPresetId": lighting,
                    "characters": scene_chars,
                    "dialogue": dialogue,
                    "soundEffectIds": beat_sfx[beat],
                    "transition": "fade" if i else "cut",
                }
            )
        title = request.get("title") or f"{lead['displayName']} and the {self._title_noun(words, seed)}"
        roles = ["protagonist", "sidekick", "friend", "mentor"]
        return {
            "schemaVersion": 1,
            "title": title[:80],
            "logline": f"{lead['displayName']} must {goal} with help from friends."[:200],
            "synopsis": (
                f"In a {tone} {request.get('genre') or 'adventure'} for {request.get('audience') or 'everyone'}, "
                f"{', '.join(c['displayName'] for c in chars)} set out to {goal}. "
                "Along the way they discover that their different powers work best together."
            )[:1200],
            "durationSeconds": duration,
            "aspectRatio": request.get("aspectRatio", "16:9"),
            "language": request.get("language", "en"),
            "characters": [
                {
                    "characterId": c["characterId"],
                    "displayName": c["displayName"],
                    "role": roles[i] if i < len(roles) else "friend",
                }
                for i, c in enumerate(chars)
            ],
            "musicCueId": music,
            "scenes": scenes,
        }

    @staticmethod
    def _goal(prompt: str) -> str:
        p = prompt.strip().rstrip(".!?")
        if not p:
            return "save the day"
        p = re.sub(r"^(a story about|story about|make|create|write)\s+", "", p, flags=re.I)
        return p[:70].lower()

    @staticmethod
    def _title_noun(words: set[str], seed: int) -> str:
        nouns = ["Glowing Map", "Missing Melody", "Sky Festival", "Secret Garden", "Moonlight Race", "Lost Spark"]
        return nouns[seed % len(nouns)]
