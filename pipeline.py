"""Local creator data, qualification, personalization, and outreach tracking."""

import csv
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEMINI_MODEL = "gemini-2.0-flash"
NOT_FOUND = "Not Found"

DATASET_FIELDS = [
    "name",
    "platform",
    "profile_url",
    "followers",
    "engagement_rate",
    "niche",
    "content_themes",
    "contact_email",
    "website",
    "audience_age",
    "audience_gender",
    "audience_geography",
    "recent_content",
    "data_source",
    "is_synthetic",
    "filter_status",
    "filter_reason",
    "email_pitch",
    "instagram_dm",
]
MESSAGE_FIELDS = [
    "name",
    "platform",
    "profile_url",
    "contact_email",
    "data_source",
    "is_synthetic",
    "email_pitch",
    "instagram_dm",
]
TRACKER_FIELDS = [
    "profile_url",
    "name",
    "contact_email",
    "data_source",
    "is_synthetic",
    "email_pitch",
    "instagram_dm",
    "delivery_status",
    "tracked_at_utc",
]

NICHE_TERMS = {
    "fashion & beauty": {
        "fashion",
        "style",
        "beauty",
        "makeup",
        "skincare",
        "skin care",
        "outfit",
        "cosmetic",
        "hair",
        "wardrobe",
    }
}


def _has_niche_relevance(influencer, target_niche):
    terms = NICHE_TERMS.get(target_niche.casefold())
    content = " ".join(
        str(influencer.get(key, ""))
        for key in ("niche", "content_themes", "recent_content", "_niche_text")
    ).casefold()
    if not terms:
        return target_niche.casefold() in content
    return any(term in content for term in terms)


def _parse_engagement(value):
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def process_and_filter_influencers(
    influencers,
    target_niche,
    min_followers=5_000,
    max_followers=100_000,
    min_engagement_rate=None,
):
    """Return all discovered records with an auditable pass/fail decision."""
    if not isinstance(influencers, list) or not target_niche:
        raise ValueError("Influencers must be a list and target_niche must be set.")
    classified = []
    for index, influencer in enumerate(influencers):
        if not isinstance(influencer, dict):
            raise ValueError(f"Influencer record {index + 1} must be an object.")
        creator = dict(influencer)
        reasons = []
        follower_count = creator.get("followers")
        try:
            follower_count = int(follower_count)
        except (TypeError, ValueError):
            follower_count = None

        relevant = _has_niche_relevance(creator, target_niche)
        if relevant:
            reasons.append("content is relevant to the target niche")
        else:
            reasons.append("content relevance to the target niche was not found")
        if follower_count is None:
            reasons.append("follower count is unavailable")
        elif min_followers <= follower_count <= max_followers:
            reasons.append(
                f"follower count is within {min_followers:,}-{max_followers:,}"
            )
        else:
            reasons.append(
                f"follower count {follower_count:,} is outside "
                f"{min_followers:,}-{max_followers:,}"
            )

        engagement = _parse_engagement(creator.get("engagement_rate"))
        if min_engagement_rate is not None:
            if engagement is None:
                reasons.append("engagement rate is unavailable")
            elif engagement >= min_engagement_rate:
                reasons.append(
                    f"engagement rate meets {min_engagement_rate:g}% minimum"
                )
            else:
                reasons.append(
                    f"engagement rate {engagement:g}% is below "
                    f"{min_engagement_rate:g}% minimum"
                )

        passed = (
            relevant
            and follower_count is not None
            and min_followers <= follower_count <= max_followers
            and (
                min_engagement_rate is None
                or (engagement is not None and engagement >= min_engagement_rate)
            )
        )
        creator["followers"] = (
            follower_count if follower_count is not None else NOT_FOUND
        )
        creator["niche"] = str(creator.get("niche") or NOT_FOUND).strip()
        creator["contact_email"] = (
            str(creator.get("contact_email") or "").strip() or NOT_FOUND
        )
        for field in (
            "name",
            "platform",
            "profile_url",
            "engagement_rate",
            "content_themes",
            "website",
            "audience_age",
            "audience_gender",
            "audience_geography",
            "recent_content",
            "data_source",
        ):
            creator[field] = (
                str(creator.get(field) or "").strip() or NOT_FOUND
            )
        creator["is_synthetic"] = bool(creator.get("is_synthetic", False))
        creator["filter_status"] = "PASSED" if passed else "FAILED"
        creator["filter_reason"] = "; ".join(reasons)
        classified.append(creator)
    return classified


def _word_count(text):
    return len(text.split())


def _fit_words(text, min_words, max_words):
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
    elif len(words) < min_words:
        text += " " + " ".join(["Thanks."] * (min_words - len(words)))
    return text


def _fallback_copy(influencer):
    name = " ".join(str(influencer.get("name") or "there").split()[:4])
    niche = str(influencer.get("niche") or "creator").strip()
    recent_content = influencer.get("recent_content")
    if recent_content and recent_content != NOT_FOUND:
        signal = " ".join(str(recent_content).split(" | ")[0].split()[:8])
        personalization = (
            f'Your recent content, "{signal}," gives us a relevant starting point'
        )
        dm_signal = signal
        recent_reference = "recent content"
    else:
        personalization = (
            f"Your profile's focus on {niche} gives us a relevant starting point"
        )
        dm_signal = niche
        recent_reference = "channel focus"

    email_pitch = (
        f"Hi {name}, I found your creator profile while researching {niche} creators. "
        f"{personalization} for a potential collaboration with viewers interested "
        f"in {niche}. We are exploring paid, affiliate, and UGC formats, with the "
        "scope shaped around your style and audience. If you are open to a "
        "conversation, could you share a media kit, preferred partnership format, "
        "and rates? I can send a short brief for you to review, with no obligation "
        "to proceed."
    )
    dm = (
        f"Hi {name}, I found your {recent_reference} about {dm_signal}. "
        f"Would you be open to discussing a {niche} collaboration?"
    )
    return {
        "email_pitch": _fit_words(email_pitch, 60, 90),
        "instagram_dm": _fit_words(dm, 15, 30),
    }


def _valid_copy(copy):
    return (
        isinstance(copy, dict)
        and isinstance(copy.get("email_pitch"), str)
        and isinstance(copy.get("instagram_dm"), str)
        and 60 <= _word_count(copy["email_pitch"]) <= 90
        and 15 <= _word_count(copy["instagram_dm"]) <= 30
    )


def generate_personalized_copy(influencer, api_key=""):
    """Generate bounded copy from observed profile signals, with a local fallback."""
    fallback = _fallback_copy(influencer)
    if not api_key:
        return fallback

    context = {
        key: influencer.get(key, NOT_FOUND)
        for key in ("name", "niche", "content_themes", "recent_content", "profile_url")
    }
    prompt = (
        "Write respectful outreach using only the creator data below. Do not invent "
        "personal details, metrics, audience traits, or recent content. Return only "
        "JSON with string fields email_pitch and instagram_dm. The email must be "
        "60-90 words and the DM 15-30 words. Email should propose a collaboration "
        "and a useful next step. Data: "
        + json.dumps(context, ensure_ascii=True)
    )
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:"
        f"generateContent?{urlencode({'key': api_key})}",
        data=json.dumps(
            {"contents": [{"parts": [{"text": prompt}]}]}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"Gemini request failed with HTTP {error.code}; "
            "check GEMINI_API_KEY and API access."
        ) from error
    except URLError as error:
        raise RuntimeError(f"Gemini request failed: {error.reason}.") from error

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        copy = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Gemini returned an unreadable outreach response.") from error
    if not _valid_copy(copy):
        raise RuntimeError(
            "Gemini response did not meet the required email and DM word counts."
        )
    return {
        "email_pitch": copy["email_pitch"].strip(),
        "instagram_dm": copy["instagram_dm"].strip(),
    }


def write_csv(output_file, fieldnames, records):
    with open(output_file, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _valid_email(value):
    return bool(
        re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value or "").strip())
    )


def run_sending_and_tracking_layer(influencers, output_file="outreach_tracker.csv"):
    """Append a simulation log once per creator; never sends real messages."""
    existing_profiles = set()
    try:
        with open(output_file, newline="", encoding="utf-8") as tracker_file:
            reader = csv.DictReader(tracker_file)
            if reader.fieldnames != TRACKER_FIELDS:
                raise RuntimeError(
                    f"Outreach tracker schema mismatch in {output_file}; "
                    "move the old tracker aside before running this version."
                )
            for row in reader:
                if row.get("profile_url"):
                    existing_profiles.add(row["profile_url"].strip().casefold())
    except FileNotFoundError:
        pass

    file_exists = False
    try:
        with open(output_file, "r", encoding="utf-8"):
            file_exists = True
    except FileNotFoundError:
        pass

    counts = {
        "tracked": 0,
        "simulated_sent": 0,
        "missing_email": 0,
        "duplicates_skipped": 0,
    }
    with open(output_file, "a", newline="", encoding="utf-8") as tracker_file:
        writer = csv.DictWriter(tracker_file, fieldnames=TRACKER_FIELDS)
        if not file_exists:
            writer.writeheader()
        for influencer in influencers:
            if influencer.get("filter_status") != "PASSED":
                continue
            profile_url = str(influencer.get("profile_url") or "").strip()
            profile_key = profile_url.casefold()
            if profile_key and profile_key in existing_profiles:
                counts["duplicates_skipped"] += 1
                continue
            email = str(influencer.get("contact_email") or NOT_FOUND).strip()
            has_email = _valid_email(email)
            status = (
                "SIMULATED_SENT"
                if has_email
                else "SIMULATED_SKIPPED_MISSING_OR_INVALID_EMAIL"
            )
            writer.writerow(
                {
                    "profile_url": profile_url,
                    "name": influencer.get("name", NOT_FOUND),
                    "contact_email": email if has_email else NOT_FOUND,
                    "data_source": influencer.get("data_source", NOT_FOUND),
                    "is_synthetic": influencer.get("is_synthetic", False),
                    "email_pitch": influencer.get("email_pitch", ""),
                    "instagram_dm": influencer.get("instagram_dm", ""),
                    "delivery_status": status,
                    "tracked_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            if profile_key:
                existing_profiles.add(profile_key)
            counts["tracked"] += 1
            counts["simulated_sent" if has_email else "missing_email"] += 1
    return counts
