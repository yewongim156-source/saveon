package com.saveon.api.quality.canonical;

import jakarta.persistence.*;

import java.time.LocalDateTime;

@Entity
@Table(
        name = "canonical_entities",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_canonical_normalized_name",
                columnNames = "normalized_name"
        )
)
public class CanonicalEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(
            name = "normalized_name",
            nullable = false,
            length = 180
    )
    private String normalizedName;

    @Column(
            name = "display_name",
            nullable = false,
            length = 180
    )
    private String displayName;

    @Column(
            name = "entity_type",
            nullable = false,
            length = 40
    )
    private String entityType;

    @Column(
            name = "verification_source",
            nullable = false,
            length = 40
    )
    private String verificationSource;

    @Column(
            name = "verification_count",
            nullable = false
    )
    private int verificationCount;

    @Column(
            name = "updated_at",
            nullable = false
    )
    private LocalDateTime updatedAt;


    protected CanonicalEntity() {
    }


    public CanonicalEntity(
            String normalizedName,
            String displayName,
            String entityType,
            String verificationSource
    ) {
        this.normalizedName = normalizedName;
        this.displayName = displayName;
        this.entityType = entityType;
        this.verificationSource = verificationSource;
        this.verificationCount = 1;
        this.updatedAt = LocalDateTime.now();
    }


    public void verifyAgain(
            String displayName,
            String entityType,
            String verificationSource
    ) {
        this.displayName = displayName;
        this.entityType = entityType;
        this.verificationSource = verificationSource;
        this.verificationCount += 1;
        this.updatedAt = LocalDateTime.now();
    }


    public Long getId() {
        return id;
    }

    public String getNormalizedName() {
        return normalizedName;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getEntityType() {
        return entityType;
    }

    public String getVerificationSource() {
        return verificationSource;
    }

    public int getVerificationCount() {
        return verificationCount;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
}
