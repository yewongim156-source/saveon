package com.saveon.api.content;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Pageable;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

public interface ContentRepository
        extends JpaRepository<Content, Long> {

    @Modifying
    @Transactional
    @Query("""
            update Content c set c.summary = :summary, c.structuredAnalysis = :structured,
                c.analyzedAt = :appliedAt
            where c.id = :id and c.status = :status and c.userEdited = false
                and c.analyzedAt = :expectedAt
            """)
    int applyEvaluationSummary(@Param("id") Long id, @Param("status") ContentStatus status,
            @Param("summary") String summary, @Param("structured") String structured,
            @Param("expectedAt") LocalDateTime expectedAt, @Param("appliedAt") LocalDateTime appliedAt);

    @Query("""
            SELECT DISTINCT c
            FROM Content c
            LEFT JOIN c.categories category
            LEFT JOIN c.keywords keyword
            LEFT JOIN c.entities entity
            WHERE
                LOWER(COALESCE(c.title, ''))
                    LIKE LOWER(CONCAT('%', :searchTerm, '%'))
                OR LOWER(COALESCE(c.summary, ''))
                    LIKE LOWER(CONCAT('%', :searchTerm, '%'))
                OR LOWER(category)
                    LIKE LOWER(CONCAT('%', :searchTerm, '%'))
                OR LOWER(keyword)
                    LIKE LOWER(CONCAT('%', :searchTerm, '%'))
                OR LOWER(entity)
                    LIKE LOWER(CONCAT('%', :searchTerm, '%'))
            ORDER BY c.createdAt DESC
            """)
    List<Content> search(
            @Param("searchTerm")
            String searchTerm
    );

    @Query("""
            SELECT c
            FROM Content c
            WHERE c.embedding IS NOT NULL
            ORDER BY cosine_distance(
                c.embedding,
                :queryEmbedding
            )
            """)
    List<Content> semanticSearch(
            @Param("queryEmbedding")
            float[] queryEmbedding,
            Pageable pageable
    );
}
