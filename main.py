"""Run the fully local creator outreach demo."""

import config
from pipeline import (
    DATASET_FIELDS,
    MESSAGE_FIELDS,
    generate_personalized_copy,
    process_and_filter_influencers,
    run_sending_and_tracking_layer,
    write_csv,
)


def main():
    if len(config.MOCK_INFLUENCERS) != 50:
        raise ValueError(
            "The local demo requires exactly 50 records in MOCK_INFLUENCERS."
        )
    discovered = [dict(creator) for creator in config.MOCK_INFLUENCERS]
    classified = process_and_filter_influencers(
        discovered,
        config.TARGET_NICHE,
        config.MIN_FOLLOWERS,
        config.MAX_FOLLOWERS,
        config.MIN_ENGAGEMENT_RATE,
    )
    qualified = [row for row in classified if row["filter_status"] == "PASSED"]
    for creator in qualified:
        creator.update(generate_personalized_copy(creator, config.GEMINI_API_KEY))

    write_csv("influencer_dataset.csv", DATASET_FIELDS, classified)
    write_csv("personalized_messages.csv", MESSAGE_FIELDS, qualified)
    tracking = run_sending_and_tracking_layer(qualified)
    failed = len(classified) - len(qualified)

    print(
        f"Loaded {len(discovered)} local demo profiles "
        f"({sum(bool(row.get('is_synthetic')) for row in discovered)} synthetic)."
    )
    print(f"Passed: {len(qualified)}; failed: {failed}")
    print(
        "Saved influencer_dataset.csv and personalized_messages.csv; "
        f"tracked {tracking['tracked']} records "
        f"({tracking['simulated_sent']} simulated email sends, "
        f"{tracking['missing_email']} skipped for missing/invalid email, "
        f"{tracking['duplicates_skipped']} duplicates skipped)."
    )
    print(
        "Delivery is simulated only. Instagram DMs are generated for manual review; "
        "no email or DM was sent."
    )
    if config.GEMINI_API_KEY:
        print("Gemini personalization was enabled via GEMINI_API_KEY.")
    else:
        print("Used the local personalization fallback; no external API was called.")


if __name__ == "__main__":
    main()
