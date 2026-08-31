# MNP API CONTRACTS V1

Representative REST contracts (framework-neutral):

POST /v1/documents
GET /v1/documents/{id}/status

GET /v1/career-card
PATCH /v1/career-card
GET /v1/career-card/versions

GET /v1/questionnaire
POST /v1/questionnaire/answers
POST /v1/match-runs
GET /v1/match-runs/{id}
GET /v1/match-runs/{id}/careers
GET /v1/careers
GET /v1/careers/{id}
GET /v1/careers/{id}/market
GET /v1/career-matches/{id}/route
GET /v1/opportunities

Admin:
POST/PATCH /v1/admin/careers
POST/PATCH /v1/admin/skills
POST /v1/admin/kb/publish
GET /v1/admin/review-queue

Every match response includes relevant version IDs and explanation codes.
