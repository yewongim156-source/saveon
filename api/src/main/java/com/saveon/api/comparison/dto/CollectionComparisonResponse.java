package com.saveon.api.comparison.dto;

import java.util.List;

public record CollectionComparisonResponse(
        boolean eligible,
        String reason,
        String comparisonEntity,
        String title,
        String summary,
        List<ComparisonFinding> commonPoints,
        List<ComparisonFinding> disagreements,
        List<ComparisonFinding> uniqueMentions,
        List<ObjectiveDisagreement> objectiveDisagreements,
        List<ExternalFact> externalFacts,
        List<Long> citedContentIds
) {
    public record Evidence(
            Long contentId,
            String title,
            String quote,
            Double timestampSeconds
    ) {
    }

    public record ComparisonFinding(
            String topic,
            String statement,
            List<Evidence> evidences
    ) {
    }

    public record ObjectiveDisagreement(
            String field,
            String label,
            String entity,
            List<String> values,
            List<Evidence> evidences
    ) {
    }

    public record ExternalFact(
            String label,
            String field,
            String entity,
            List<String> savedValues,
            String status,
            String currentValue,
            String explanation,
            String checkedAt,
            List<ExternalSource> sources
    ) {
    }

    public record ExternalSource(
            String title,
            String url
    ) {
    }
}
