package com.saveon.api.quality.canonical;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CanonicalEntityRepository
        extends JpaRepository<CanonicalEntity, Long> {

    Optional<CanonicalEntity> findByNormalizedName(
            String normalizedName
    );
}
