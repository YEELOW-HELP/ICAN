# MNP DATABASE SCHEMA V1 - IMPLEMENTATION BLUEPRINT

Recommended PostgreSQL.

Core tables:
users
assessment_sessions
source_documents
career_cards
career_card_versions
experiences
achievements
educations
credentials
languages
evidence
skills
skill_aliases
person_skills
knowledge
person_knowledge
career_goals
income_targets
preference_profiles
work_values
person_work_values
constraints
learning_capacity
career_families
careers
career_aliases
career_tasks
career_skill_requirements
career_knowledge_requirements
career_requirements
career_attributes
career_relations
external_mappings
market_snapshots
salary_snapshots
match_runs
career_matches
match_components
feasibility_findings
personal_gaps
career_routes
route_steps
learning_opportunities
opportunities
audit_log
data_source_versions

All important records: UUID/id, created_at, updated_at as appropriate.
Use foreign keys; archive canonical taxonomy rather than hard delete.
Store methodology/engine/KB/market versions on MatchRun.
Physical migrations are produced only after schema review against ORM/framework choice.
