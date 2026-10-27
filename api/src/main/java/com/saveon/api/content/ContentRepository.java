package com.saveon.api.content;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

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
}