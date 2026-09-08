# MNP MATCHING MATH V1

## Output
A multidimensional Match Vector, not one user-facing percentage.

## Components
- Skill Fit
- Experience Transfer
- Knowledge Fit
- Preference Fit
- Values Fit
- Feasibility
- Market Attractiveness
- Income Potential
- Transition Cost
- Confidence (separate quality dimension)

## Skill Fit
Weighted coverage of career requirements by PersonSkills, considering proficiency and evidence strength. UNKNOWN is not scored as confirmed absence.

## Experience Transfer
Compare functions/tasks, responsibility scope, domain proximity, management, tools, stakeholders, complexity and seniority.

## Knowledge Fit
Required knowledge vs PersonKnowledge.

## Preference/Values
Compare structured Career Context/Attributes with user preferences and ranked values.

## Overall ranking
Internal aggregate may combine normalized components, but weights are configuration, versioned, and calibrated using Golden Dataset/pilot outcomes.

## Critical rule
Confidence is not simply another fit score. It gates/tie-breaks and qualifies recommendations.

## User UI
Bands/components/explanations; no fake probability or raw aggregate score in V1.
