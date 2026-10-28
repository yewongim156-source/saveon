# pgvector setup

The development compose file uses `pgvector/pgvector:pg16` and enables the
`vector` extension for a new database volume.

If the existing `saveon_postgres_data` volume was created before pgvector was
added, run the extension command once after starting the new image:

```powershell
docker compose exec postgres psql -U saveon -d saveon -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The application stores one normalized 768-dimensional embedding per completed
content. Semantic search is available at:

```text
GET /api/v1/contents/search/semantic?q=서울에서 데이트할 카페&limit=10
```

The initial implementation uses exact cosine search. Add an HNSW index only
after a representative amount of data exists and recall has been measured.
