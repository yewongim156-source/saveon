package com.saveon.api.content;

import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "contents")
public class Content {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 2000)
    private String sourceUrl;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ContentPlatform platform;

    private String title;

    @Column(columnDefinition = "TEXT")
    private String summary;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ContentStatus status;

    @Column(nullable = false)
    private LocalDateTime createdAt;

    private LocalDateTime analyzedAt;


    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(
            name = "content_categories",
            joinColumns = @JoinColumn(name = "content_id")
    )
    @Column(name = "category")
    private List<String> categories = new ArrayList<>();


    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(
            name = "content_keywords",
            joinColumns = @JoinColumn(name = "content_id")
    )
    @Column(name = "keyword")
    private List<String> keywords = new ArrayList<>();


    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(
            name = "content_entities",
            joinColumns = @JoinColumn(name = "content_id")
    )
    @Column(name = "entity")
    private List<String> entities = new ArrayList<>();


    protected Content() {
    }


    public Content(
            String sourceUrl,
            ContentPlatform platform
    ) {
        this.sourceUrl = sourceUrl;
        this.platform = platform;
        this.status = ContentStatus.PENDING;
        this.createdAt = LocalDateTime.now();
    }


    public void startAnalysis() {
        this.status = ContentStatus.ANALYZING;
    }


    public void completeAnalysis(
            String title,
            String summary,
            List<String> categories,
            List<String> keywords,
            List<String> entities
    ) {
        this.title = title;
        this.summary = summary;

        this.categories.clear();
        this.categories.addAll(categories);

        this.keywords.clear();
        this.keywords.addAll(keywords);

        this.entities.clear();
        this.entities.addAll(entities);

        this.status = ContentStatus.COMPLETED;
        this.analyzedAt = LocalDateTime.now();
    }


    public void failAnalysis() {
        this.status = ContentStatus.FAILED;
        this.analyzedAt = LocalDateTime.now();
    }


    public Long getId() {
        return id;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public ContentPlatform getPlatform() {
        return platform;
    }

    public String getTitle() {
        return title;
    }

    public String getSummary() {
        return summary;
    }

    public ContentStatus getStatus() {
        return status;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public LocalDateTime getAnalyzedAt() {
        return analyzedAt;
    }

    public List<String> getCategories() {
        return categories;
    }

    public List<String> getKeywords() {
        return keywords;
    }

    public List<String> getEntities() {
        return entities;
    }
}