"""Tests for Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.2): corroboration
clustering + credibility scoring."""

from src.engines.news_credibility import (
    ClusterCandidate,
    classify_non_consensus,
    compute_credibility_score,
    find_cluster_match,
    source_trust_weight,
)


class TestSourceTrustWeight:

    def test_known_tiers(self):
        assert source_trust_weight("WIRE") == 1.00
        assert source_trust_weight("TIER1") == 0.85
        assert source_trust_weight("PR") == 0.70
        assert source_trust_weight("TIER2") == 0.55
        assert source_trust_weight("BLOG") == 0.35
        assert source_trust_weight("SOCIAL") == 0.20

    def test_case_insensitive(self):
        assert source_trust_weight("wire") == source_trust_weight("WIRE")

    def test_unknown_tier_falls_back_to_default(self):
        assert source_trust_weight("SOMETHING_NEW") == 0.40

    def test_none_tier_falls_back_to_default(self):
        assert source_trust_weight(None) == 0.40


class TestFindClusterMatch:

    def test_url_match(self):
        candidate = ClusterCandidate(id="2", source_url="https://reuters.com/a", title="Different title")
        existing = [ClusterCandidate(id="1", source_url="https://reuters.com/a", title="Original title")]
        match = find_cluster_match(candidate, existing)
        assert match is not None
        assert match.id == "1"

    def test_url_match_case_insensitive(self):
        candidate = ClusterCandidate(id="2", source_url="HTTPS://Reuters.com/A", title="X")
        existing = [ClusterCandidate(id="1", source_url="https://reuters.com/a", title="Y")]
        assert find_cluster_match(candidate, existing) is not None

    def test_title_jaccard_match(self):
        candidate = ClusterCandidate(
            id="2", source_url="https://apnews.com/b",
            title="Fed raises interest rates by quarter point",
        )
        existing = [ClusterCandidate(
            id="1", source_url="https://reuters.com/a",
            title="Fed raises interest rates quarter point today",
        )]
        match = find_cluster_match(candidate, existing)
        assert match is not None
        assert match.id == "1"

    def test_content_simhash_match(self):
        body = "The company reported record quarterly revenue driven by strong cloud demand and enterprise growth."
        candidate = ClusterCandidate(id="2", source_url="https://siteb.com/x", title="Totally different headline", body_text=body)
        existing = [ClusterCandidate(id="1", source_url="https://sitea.com/y", title="Another unrelated headline", body_text=body)]
        match = find_cluster_match(candidate, existing)
        assert match is not None
        assert match.id == "1"

    def test_no_match_for_unrelated_articles(self):
        candidate = ClusterCandidate(id="2", source_url="https://siteb.com/x", title="Local weather forecast for the weekend")
        existing = [ClusterCandidate(id="1", source_url="https://sitea.com/y", title="Central bank raises benchmark interest rate")]
        assert find_cluster_match(candidate, existing) is None

    def test_empty_existing_returns_none(self):
        candidate = ClusterCandidate(id="1", source_url="https://a.com/x", title="Some headline")
        assert find_cluster_match(candidate, []) is None


class TestComputeCredibilityScore:

    def test_single_source_no_boost(self):
        score = compute_credibility_score(tier="WIRE", corroboration_count=1)
        assert score == 1.00

    def test_corroboration_boosts_score(self):
        low = compute_credibility_score(tier="TIER2", corroboration_count=1)
        high = compute_credibility_score(tier="TIER2", corroboration_count=3)
        assert high > low

    def test_boost_is_capped(self):
        # Even with many corroborating sources, score never exceeds 1.0.
        score = compute_credibility_score(tier="WIRE", corroboration_count=50)
        assert score == 1.0

    def test_unknown_tier_uses_default_weight(self):
        assert compute_credibility_score(tier=None, corroboration_count=1) == 0.40


class TestClassifyNonConsensus:

    def test_low_tier_uncorroborated_is_non_consensus(self):
        assert classify_non_consensus(tier="BLOG", corroboration_count=1) is True

    def test_low_tier_corroborated_is_not_non_consensus(self):
        assert classify_non_consensus(tier="BLOG", corroboration_count=2) is False

    def test_wire_tier_is_never_non_consensus(self):
        assert classify_non_consensus(tier="WIRE", corroboration_count=1) is False

    def test_unknown_tier_uncorroborated_is_non_consensus(self):
        assert classify_non_consensus(tier=None, corroboration_count=1) is True
