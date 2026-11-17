package com.saveon.api.quality.correction;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface AiCorrectionRepository
        extends JpaRepository<AiCorrection, Long> {

    List<AiCorrection> findByContentIdOrderByCreatedAtDesc(
            Long contentId
    );

    @Query("""
            SELECT c.errorType, COUNT(c)
            FROM AiCorrection c
            GROUP BY c.errorType
            ORDER BY COUNT(c) DESC
            """)
    List<Object[]> countByErrorType();
}
