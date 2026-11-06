package com.saveon.api.quality.correction;

import jakarta.persistence.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "ai_corrections")
public class AiCorrection {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "content_id")
    private Long contentId;

    @Column(
            name = "correction_source",
            nullable = false,
            length = 40
    )
    private String correctionSource;

    @Column(
            name = "field_name",
            nullable = false,
            length = 80
    )
    private String fieldName;

    @Column(
            name = "ai_value",
            columnDefinition = "TEXT"
    )
    private String aiValue;

    @Column(
            name = "corrected_value",
            columnDefinition = "TEXT"
    )
    private String correctedValue;

    @Column(
            name = "error_type",
            nullable = false,
            length = 80
    )
    private String errorType;

    @Column(
            name = "created_at",
            nullable = false
    )
    private LocalDateTime createdAt;


    protected AiCorrection() {
    }


    public AiCorrection(
            Long contentId,
            String correctionSource,
            String fieldName,
            String aiValue,
            String correctedValue,
            String errorType
    ) {
        this.contentId = contentId;
        this.correctionSource = correctionSource;
        this.fieldName = fieldName;
        this.aiValue = aiValue;
        this.correctedValue = correctedValue;
        this.errorType = errorType;
        this.createdAt = LocalDateTime.now();
    }


    public Long getId() {
        return id;
    }

    public Long getContentId() {
        return contentId;
    }

    public String getCorrectionSource() {
        return correctionSource;
    }

    public String getFieldName() {
        return fieldName;
    }

    public String getAiValue() {
        return aiValue;
    }

    public String getCorrectedValue() {
        return correctedValue;
    }

    public String getErrorType() {
        return errorType;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}
