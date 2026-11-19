package com.saveon.api.content;

import jakarta.persistence.*;
import org.hibernate.annotations.Array;
import org.hibernate.annotations.ColumnDefault;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

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

    @Column(name = "structured_analysis", columnDefinition = "TEXT")
    private String structuredAnalysis;

    @Column(name = "user_edited", nullable = false)
    @ColumnDefault("false")
    private boolean userEdited = false;

    @Column(name = "edited_at")
    private LocalDateTime editedAt;

    @Column(name = "embedding_model")
    private String embeddingModel;

    @Column(name = "embedding_text", columnDefinition = "TEXT")
    private String embeddingText;

    @JdbcTypeCode(SqlTypes.VECTOR)
    @Array(length = 768)
    @Column(columnDefinition = "vector(768)")
    private float[] embedding;


    // Explicit per-Reel opt-in: never silently cache other creators' frames.
    @Column(name = "thumbnail_allowed")
    private Boolean thumbnailAllowed = Boolean.FALSE;

    @Column(name = "thumbnail_object_key", length = 250)
    private String thumbnailObjectKey;

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
            List<String> entities,
            String structuredAnalysis
    ) {
        replaceAnalysisData(
                title,
                summary,
                categories,
                keywords,
                entities,
                structuredAnalysis
        );

        this.userEdited = false;
        this.editedAt = null;
        this.status = ContentStatus.COMPLETED;
        this.analyzedAt = LocalDateTime.now();
    }


    public void applyUserCorrection(
            String title,
            String summary,
            List<String> categories,
            List<String> keywords,
            List<String> entities,
            String structuredAnalysis
    ) {
        replaceAnalysisData(
                title,
                summary,
                categories,
                keywords,
                entities,
                structuredAnalysis
        );

        this.userEdited = true;
        this.editedAt = LocalDateTime.now();
    }


    public void applySystemCorrection(
            String title,
            String summary,
            List<String> categories,
            List<String> keywords,
            List<String> entities,
            String structuredAnalysis
    ) {
        replaceAnalysisData(
                title,
                summary,
                categories,
                keywords,
                entities,
                structuredAnalysis
        );
    }


    private void replaceAnalysisData(
            String title,
            String summary,
            List<String> categories,
            List<String> keywords,
            List<String> entities,
            String structuredAnalysis
    ) {
        List<String> categoryCopy =
                categories != null
                        ? new ArrayList<>(categories)
                        : List.of();

        List<String> keywordCopy =
                keywords != null
                        ? new ArrayList<>(keywords)
                        : List.of();

        List<String> entityCopy =
                entities != null
                        ? new ArrayList<>(entities)
                        : List.of();

        this.title = title;
        this.summary = summary;

        this.categories.clear();
        this.categories.addAll(categoryCopy);

        this.keywords.clear();
        this.keywords.addAll(keywordCopy);

        this.entities.clear();
        this.entities.addAll(entityCopy);

        this.structuredAnalysis = structuredAnalysis;
    }


    public void failAnalysis() {
        this.status = ContentStatus.FAILED;
        this.analyzedAt = LocalDateTime.now();
    }


    /**
     * 재분석이 임시 오류(모델 과부하 등)로 대체 결과만 내놓았을 때,
     * 이전에 저장된 분석 결과를 그대로 두고 완료 상태로 되돌린다.
     */
    public boolean keepPreviousAnalysis() {
        if (this.summary == null || this.summary.isBlank()) {
            return false;
        }

        this.status = ContentStatus.COMPLETED;
        return true;
    }


    public void setEmbedding(
            float[] embedding,
            String embeddingModel,
            String embeddingText
    ) {
        this.embedding = embedding;
        this.embeddingModel = embeddingModel;
        this.embeddingText = embeddingText;
    }


    public void setThumbnailAllowed(boolean permitted) {
        this.thumbnailAllowed = permitted;
    }

    public boolean isThumbnailAllowed() {
        return Boolean.TRUE.equals(thumbnailAllowed);
    }

    public void setThumbnailObjectKey(String key) {
        this.thumbnailObjectKey = key;
    }

    public String storedThumbnailKey() {
        return thumbnailObjectKey;
    }

    public boolean isThumbnailAvailable() {
        return thumbnailObjectKey != null && !thumbnailObjectKey.isBlank();
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

    public String getStructuredAnalysis() {
        return structuredAnalysis;
    }

    public boolean isUserEdited() {
        return userEdited;
    }

    public LocalDateTime getEditedAt() {
        return editedAt;
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
// SAVEON_INSTAGRAM_THUMBNAIL_V1
