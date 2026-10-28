package com.saveon.api.content;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Pageable;

import java.util.List;

public interface ContentRepository
        extends JpaRepository<Content, Long> {

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
