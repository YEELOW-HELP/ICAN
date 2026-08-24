# Canonical ERD v3.1

```mermaid
erDiagram
  USER ||--o{ MEMBERSHIP : has
  TENANT ||--o{ MEMBERSHIP : contains
  USER ||--o{ CONSENT : grants
  USER ||--o{ INTERVIEW_SESSION : starts
  INTERVIEW_SESSION ||--o{ ANSWER : contains
  ANSWER ||--o{ EVIDENCE : produces
  USER ||--|| POTENTIAL_PROFILE : owns
  POTENTIAL_PROFILE ||--o{ PROFILE_CLAIM : contains
  PROFILE_CLAIM }o--o{ EVIDENCE : grounded_by
  USER ||--o{ GOAL : has
  USER ||--o{ CONSTRAINT : has
  USER ||--o{ EXPERIENCE : has
  USER ||--o{ USER_SKILL : has
  SKILL ||--o{ USER_SKILL : classifies

  CAREER ||--o{ CAREER_SKILL : requires
  SKILL ||--o{ CAREER_SKILL : maps
  CAREER ||--o{ CAREER_EDGE : from
  CAREER ||--o{ CAREER_EDGE : to
  CAREER ||--o{ MARKET_SIGNAL : has

  USER ||--o{ SCENARIO : receives
  CAREER ||--o{ SCENARIO : anchors
  SCENARIO ||--o{ SCENARIO_SCORE : scored_by
  USER ||--o{ DIRECTION_DECISION : makes
  DIRECTION_DECISION }o--|| SCENARIO : chooses

  USER ||--o{ ROADMAP : owns
  ROADMAP ||--o{ ROADMAP_VERSION : versions
  ROADMAP_VERSION ||--o{ MILESTONE : contains
  MILESTONE ||--o{ TASK : contains
  TASK ||--o{ TASK_EVIDENCE : proves

  OPPORTUNITY ||--o{ OPPORTUNITY_SKILL : needs
  SKILL ||--o{ OPPORTUNITY_SKILL : maps
  USER ||--o{ OPPORTUNITY_MATCH : receives
  OPPORTUNITY ||--o{ OPPORTUNITY_MATCH : ranked
  OPPORTUNITY_MATCH ||--o| APPLICATION : may_create

  USER ||--o{ CLIENT_RELATIONSHIP : client
  GUIDE_PROFILE ||--o{ CLIENT_RELATIONSHIP : guide
  CLIENT_RELATIONSHIP ||--o{ GUIDE_SESSION : has
  GUIDE_SESSION ||--o{ GUIDE_NOTE : has

  USER ||--o{ OUTCOME_EVENT : produces
  ROADMAP ||--o{ OUTCOME_EVENT : linked
  OPPORTUNITY ||--o{ OUTCOME_EVENT : linked

  GUIDE_PROFILE ||--o{ REFERRAL : owns
  REFERRAL ||--o{ ATTRIBUTION : creates
  PAYMENT ||--o{ ATTRIBUTION : attributed
  PAYMENT ||--o{ COMMISSION : generates
  GUIDE_PROFILE ||--o{ COMMISSION : earns

  USER {
    uuid id PK
    string email
    string phone
    string locale
    string timezone
    datetime created_at
    datetime deleted_at
  }
  TENANT {
    uuid id PK
    string type
    string name
    string status
  }
  MEMBERSHIP {
    uuid id PK
    uuid user_id FK
    uuid tenant_id FK
    string role
  }
  CONSENT {
    uuid id PK
    uuid user_id FK
    string purpose
    string version
    datetime granted_at
    datetime withdrawn_at
  }
  INTERVIEW_SESSION {
    uuid id PK
    uuid user_id FK
    string status
    string assessment_version
    json completeness
  }
  ANSWER {
    uuid id PK
    uuid session_id FK
    string question_id
    text answer_text
  }
  EVIDENCE {
    uuid id PK
    uuid user_id FK
    string source_type
    uuid source_ref
    string claim_key
    float weight
    float confidence
  }
  POTENTIAL_PROFILE {
    uuid id PK
    uuid user_id FK
    int version
    string model_version
    datetime generated_at
  }
  PROFILE_CLAIM {
    uuid id PK
    uuid profile_id FK
    string dimension
    string label
    float score
    float confidence
  }
  CAREER {
    uuid id PK
    string taxonomy_ref
    string title_uk
    string title_en
    string status
  }
  SCENARIO {
    uuid id PK
    uuid user_id FK
    uuid career_id FK
    string scenario_type
    float fit_score
    float confidence
  }
  DIRECTION_DECISION {
    uuid id PK
    uuid user_id FK
    uuid scenario_id FK
    text rationale
    datetime selected_at
  }
  ROADMAP {
    uuid id PK
    uuid user_id FK
    uuid direction_decision_id FK
    string status
  }
  ROADMAP_VERSION {
    uuid id PK
    uuid roadmap_id FK
    int version
    string reason
  }
  TASK {
    uuid id PK
    uuid milestone_id FK
    string type
    string status
    datetime due_at
  }
  OPPORTUNITY {
    uuid id PK
    string type
    string title
    string source_name
    string source_url
    datetime verified_at
    string status
  }
  OPPORTUNITY_MATCH {
    uuid id PK
    uuid user_id FK
    uuid opportunity_id FK
    float fit_score
    float confidence
    string status
  }
  GUIDE_PROFILE {
    uuid id PK
    uuid user_id FK
    string level
    string certification_status
  }
  CLIENT_RELATIONSHIP {
    uuid id PK
    uuid client_user_id FK
    uuid guide_id FK
    string stage
    string status
  }
  GUIDE_SESSION {
    uuid id PK
    uuid relationship_id FK
    datetime starts_at
    string status
  }
  OUTCOME_EVENT {
    uuid id PK
    uuid user_id FK
    string type
    json value
    datetime occurred_at
  }
  PAYMENT {
    uuid id PK
    uuid user_id FK
    int amount_minor
    string currency
    string status
  }
  COMMISSION {
    uuid id PK
    uuid payment_id FK
    uuid guide_id FK
    int amount_minor
    string status
  }
```

## Database rules

1. Critical business data must be relational; JSON is for flexible snapshots, not the only source of truth.
2. Every changing recommendation object has a `version` or immutable history record.
3. Deletes of user data follow privacy workflow; audit/security records follow separate retention rules.
4. Money is stored in minor units + currency.
5. Timestamps are UTC; user timezone is presentation metadata.
6. Foreign keys and tenant ownership are enforced server-side.
7. AI trace/model/prompt versions are stored against generated artifacts.
