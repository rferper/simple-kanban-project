# NextLane — Project Source of Truth

> **Product name:** NextLane.  
> **Document purpose:** This file is the authoritative product and implementation guide for the project.  
> **Primary audience:** AI coding agent + developer.  
> **Project type:** Weekend personal project / AI-development course project / portfolio project.  
> **Primary user:** An academic researcher actively trying to move into industry while still managing their current academic workload.  
> **Platform:** Responsive web application.  
> **Technology stack:** Intentionally unspecified for now. The course requirements will determine the implementation stack later.

---

# 1. Product Definition

## 1.1 Working concept

The app is called **NextLane**. Use this name everywhere the product is named: UI titles, page and document titles, README, and portfolio material.

NextLane is a focused productivity application for academics moving into industry.

The user must simultaneously manage three competing areas:

1. **Current Job** — research, teaching, reviews, administration, papers, experiments, meetings, grants, etc.
2. **Job Search** — discovering roles, preparing applications, applying, interviewing, and tracking outcomes.
3. **Learning / Pivot** — developing the skills, projects, courses, interview preparation, and portfolio work required to transition into industry.

The application should combine:

- a lightweight Kanban workflow,
- a unified overview of all three areas,
- simple workload planning,
- a specialised job-application tracker,
- visually pleasant and motivating presentation,
- optional AI assistance for turning job adverts into structured job cards.

NextLane is **not** a generic project-management platform.

The central product question is:

> **What should I work on today to maximise my chances of successfully moving into industry without neglecting my current job?**

---

# 2. Target User

## 2.1 Primary persona

An academic researcher who:

- currently has a full-time academic role;
- is considering or actively pursuing a move into industry;
- applies to research, engineering, data, ML, AI, or adjacent roles;
- must continue delivering academic responsibilities during the transition;
- is learning technical or professional skills for the pivot;
- may have several applications in different stages at once;
- may struggle with prioritisation because all three areas compete for limited time.

Example tasks could include:

### Current Job

- Finish paper revision
- Run experiments
- Review a paper
- Prepare a lecture
- Submit travel reimbursement
- Prepare conference slides
- Write a grant section
- Attend project meeting
- Update research code

### Job Search

- Review Anthropic Research Engineer advert
- Update CV for role
- Submit application
- Prepare recruiter screen
- Prepare coding interview
- Follow up with contact
- Research company
- Record rejection / offer

### Learning / Pivot

- Complete system-design module
- Practise LeetCode
- Finish Docker tutorial
- Build portfolio project
- Learn deployment basics
- Read industry ML engineering material
- Improve GitHub portfolio
- Continue AI-development course

---

# 3. Product Principles

All implementation decisions should follow these principles.

## 3.1 Specialised, not generic

The app must visibly feel designed for career transition.

Do not reproduce Trello, Jira, Notion, or Todoist feature-for-feature.

Every major feature should help with at least one of:

- balancing current work and career transition;
- tracking job applications;
- deciding what deserves attention;
- connecting skill development to target jobs;
- making the transition feel manageable.

## 3.2 Unified but structured

The three areas must remain distinct:

- Current Job
- Job Search
- Learning / Pivot

However, the user must also be able to understand their entire workload from one screen.

Do **not** make the user constantly switch between three unrelated boards.

## 3.3 Low friction

Adding a task should take only a few seconds.

Most card fields must be optional.

A user should not have to fill a form with ten fields simply to add:

> Review paper

## 3.4 Cute and motivating, but not childish

The visual direction should be:

- warm,
- soft,
- modern,
- friendly,
- calm,
- slightly playful,
- visually rewarding.

Avoid:

- corporate Jira aesthetics;
- dense enterprise dashboards;
- childish cartoon interfaces;
- excessive gamification;
- aggressive productivity guilt;
- red warning-heavy screens.

## 3.5 MVP discipline

This is initially a weekend / course project.

Prefer one excellent workflow over ten unfinished features.

Do not add features outside the MVP unless explicitly requested.

---

# 4. Information Architecture

The application should initially have four main destinations:

1. **Dashboard**
2. **Current Job**
3. **Job Search**
4. **Learning**

Optional later pages:

- Analytics
- Settings
- Archive

For the MVP, these optional pages should either be very small or postponed.

---

# 5. Main Dashboard

## 5.1 Purpose

The Dashboard is the default landing page.

It provides one unified visual overview of the user's current situation.

The dashboard must answer:

- What is currently important?
- What deadlines are approaching?
- Am I spending too much time in one area?
- What should I work on next?
- Which job applications need action?
- What learning tasks are actually relevant?

## 5.2 Main layout

Use **three vertical columns**:

| Current Job | Job Search | Learning / Pivot |
|-------------|------------|------------------|

Each column displays a compact list of the most relevant active cards from that area.

This is **not** the full Kanban board.

It is a prioritised dashboard view.

Suggested ordering inside each column:

1. overdue items;
2. urgent / high-priority items;
3. items due soon;
4. items currently in progress;
5. other active items.

Each column should initially show approximately 3–6 cards.

Provide a clear action to:

> View full board

## 5.3 Dashboard header

At the top of the dashboard, show a compact summary.

Example:

```text
Good morning 👋

This week
14.5h planned / 18h available

Current Job      7h
Job Search       4.5h
Learning         3h
```

The weekly-hours feature should remain intentionally simple.

No calendar scheduling algorithm is required.

## 5.4 Weekly available hours

The user may optionally enter:

> Available focused hours this week

Example:

```text
18 hours
```

The app calculates:

```text
sum(estimated hours of cards marked for this week)
```

Display:

- total planned hours;
- available hours;
- difference;
- a gentle warning if overloaded.

Examples:

```text
14h planned / 18h available
4h still available
```

or:

```text
22h planned / 18h available
4h over capacity
```

Do not build:

- automatic scheduling;
- calendar optimisation;
- time-blocking;
- complex forecasting.

This feature is a **capacity indicator**, not a scheduling engine.

## 5.5 Focus section

Near the top of the dashboard, include:

> **Focus today**

Display up to 3 recommended cards.

For MVP, this does **not** require AI.

Use a deterministic priority rule.

Suggested scoring logic:

```text
1. overdue
2. due today
3. high priority + due soon
4. currently in progress
5. high priority
6. medium priority + upcoming deadline
```

Prefer diversity across the three areas where reasonable.

Example:

```text
Focus today

1. Finish paper rebuttal       Current Job     2h
2. Submit Company X application Job Search     1h
3. System design module         Learning        1h
```

Do not claim that these are mathematically optimal recommendations.

They are simply the app's suggested focus items.

---

# 6. Full Kanban Boards

Each area gets its own full board.

---

# 7. Current Job Board

## 7.1 Columns

Use:

```text
Backlog
This Week
In Progress
Waiting
Done
```

## 7.2 Allowed tasks

Anything related to the user's academic job is valid.

Examples:

- research,
- teaching,
- paper writing,
- reviews,
- meetings,
- experiments,
- grant writing,
- administration,
- supervision,
- conference preparation,
- service tasks.

Do not artificially restrict this category.

---

# 8. Job Search Board

## 8.1 Columns

Use:

```text
Interesting
Preparing
Applied
Interview
Offer
```

Rejected and withdrawn applications should go to an **Archive** instead of occupying permanent main-board columns.

A job may therefore have an outcome such as:

```text
active
rejected
withdrawn
accepted
declined
```

The board itself should prioritise active opportunities.

## 8.2 Job card visual content

A collapsed job card should show only high-value information:

```text
Company
Role
Priority
Stage
Deadline or next interview date
Estimated effort
Optional location
```

Example:

```text
Anthropic
Research Engineer

⭐ Dream role
Interview · 18 Sep
Prep: 3h
London / Hybrid
```

Do not overload collapsed cards with every stored field.

---

# 9. Learning / Pivot Board

## 9.1 Columns

Use:

```text
Ideas
Planned
Learning
Practising
Done
```

## 9.2 Valid learning cards

A learning card can represent:

- a skill;
- a course;
- a project;
- an interview-preparation topic;
- a portfolio improvement;
- a coding-practice goal;
- a reading objective;
- another activity relevant to the career transition.

Examples:

```text
Learn Docker
Complete system design course
Practise graph problems
Build RAG demo
Improve portfolio README
Finish AI-dev course module
```

## 9.3 Connection to jobs

Learning cards may optionally be linked to one or more job cards.

Example:

```text
System Design

Relevant for:
- Anthropic Research Engineer
- DeepMind Research Engineer
```

This relationship is important.

It prevents the Learning board from becoming an unrelated collection of courses.

---

# 10. Card Model

All three boards should use one shared base card model.

Conceptually:

```text
Card
├── id
├── title
├── description
├── area
├── status
├── priority
├── deadline
├── estimatedHours
├── plannedThisWeek
├── tags[]
├── subtasks[]
├── createdAt
├── updatedAt
└── completedAt
```

## 10.1 Area

Allowed values:

```text
CURRENT_JOB
JOB_SEARCH
LEARNING
```

## 10.2 Priority

Allowed values:

```text
LOW
MEDIUM
HIGH
URGENT
```

Visually, avoid making everything look alarmist.

Suggested semantics:

- Low — muted
- Medium — normal
- High — visually emphasised
- Urgent — strongest emphasis

## 10.3 Estimated hours

Optional numeric value.

Examples:

```text
0.5
1
1.5
2
4
```

The application may show friendly labels such as:

```text
30m
1h
1h 30m
```

No detailed time-tracking functionality is required.

## 10.4 Deadline

Optional date.

Cards without deadlines are valid.

## 10.5 Planned this week

Boolean:

```text
true / false
```

Cards marked for this week contribute to the weekly workload calculation.

## 10.6 Tags

Optional free-form labels.

Examples:

```text
paper
teaching
AI safety
coding
interview
portfolio
course
```

---

# 11. Job-Specific Data

A Job Search card may have additional structured information.

Conceptual model:

```text
JobDetails
├── cardId
├── company
├── role
├── jobUrl
├── location
├── salaryText
├── workMode
├── contactName
├── contactDetails
├── jobDescription
├── requirements[]
├── niceToHave[]
├── applicationDeadline
├── interviewDate
├── cvVersion
├── fit
├── outcome
├── notes
└── relatedLearningCardIds[]
```

Most fields are optional.

## 11.1 Fit

Suggested values:

```text
LOW
MEDIUM
HIGH
DREAM
```

Use friendly visual terminology where appropriate.

For example:

```text
Good fit
Strong fit
Dream role
```

## 11.2 Work mode

Suggested values:

```text
ONSITE
HYBRID
REMOTE
UNKNOWN
```

---

# 12. Card Detail View

Clicking a card should open a detail interface.

Use either:

- a side drawer, or
- a modal.

A drawer is preferable on desktop because the board remains visible.

## 12.1 Base task detail

Show:

```text
Title
Description
Area
Status
Priority
Deadline
Estimated time
Planned this week
Tags
Subtasks
```

Provide:

```text
Edit
Delete
Archive
Mark complete
```

depending on card type and status.

## 12.2 Job detail

Additionally show:

```text
Company
Role
Job URL
Location
Salary
Fit
Job advert / description
Requirements
Nice-to-have requirements
Application deadline
Interview date
CV version
Contact
Related learning cards
Notes
```

---

# 13. Quick Add

Adding a normal task must be fast.

Each board should have a clear:

```text
+ Add card
```

Minimum required field:

```text
Title
```

Everything else should be optional.

After creation, the user can enrich the card.

Do not force users through a multi-step wizard for ordinary tasks.

---

# 14. Drag and Drop

The full boards should support drag and drop between columns.

Dragging a card changes its status.

Example:

```text
Preparing → Applied
```

The UI should update immediately.

Persist the new state.

If drag and drop becomes technically expensive under course constraints, simple move controls can temporarily substitute during early development, but drag and drop is part of the intended polished MVP.

---

# 15. AI Feature — Job Advert Import

This is the only AI feature required for the initial version.

## 15.1 User flow

From the Job Search board:

```text
+ Add job
```

Provide two options:

```text
Create manually
Paste job advert
```

For "Paste job advert":

1. user pastes job advert text;
2. user clicks **Generate job card**;
3. AI extracts structured information;
4. user sees a preview;
5. user can edit the extracted information;
6. user confirms;
7. job card is created in `Interesting` by default.

## 15.2 AI extraction target

Attempt to extract:

```text
company
role
location
salaryText
workMode
applicationDeadline
requirements[]
niceToHave[]
short summary
suggested tags[]
```

Optionally:

```text
fit notes
```

However, fit must not be presented as objective unless the app later has structured user-profile data.

For MVP, do **not** automatically score candidate suitability.

## 15.3 AI failure behaviour

AI output must never be blindly committed.

The user must receive an editable preview.

If extraction fails:

- preserve the pasted advert;
- show a friendly error;
- allow manual creation.

Do not block the rest of the application if AI functionality is unavailable.

The Kanban must remain fully usable without AI.

---

# 16. Visual Design Direction

## 16.1 Overall mood

The interface should feel:

> cosy productivity for an ambitious career transition

Keywords:

- soft
- clean
- friendly
- polished
- calm
- cute
- optimistic
- spacious

Do not interpret "cute" as childish.

## 16.2 Visual hierarchy

Use:

- rounded cards;
- generous spacing;
- subtle shadows;
- soft section backgrounds;
- small icons;
- friendly empty states;
- restrained animation;
- clear typography.

Avoid:

- sharp enterprise tables everywhere;
- excessive borders;
- saturated warning colours;
- visual clutter;
- tiny text;
- dense information panels.

## 16.3 Area identities

Give each area a consistent visual identity.

Suggested direction:

### Current Job

Icon:

```text
🎓
```

Visual family:

```text
soft lavender / purple
```

### Job Search

Icon:

```text
🚀
```

Visual family:

```text
soft peach / coral / warm orange
```

### Learning

Icon:

```text
🌱
```

Visual family:

```text
soft mint / green
```

These colours are suggestions, not mandatory exact hex values.

The final palette must maintain accessible contrast.

## 16.4 Background

Prefer:

- warm off-white;
- very pale neutral;
- subtle tinted background.

Avoid pure bright white everywhere if it makes the product feel sterile.

## 16.5 Card appearance

Cards should visually communicate:

- title;
- area;
- priority;
- deadline;
- estimated effort.

Secondary metadata should be visually subdued.

Do not put ten badges on every card.

## 16.6 Micro-interactions

Use small, tasteful animations for:

- moving cards;
- completing cards;
- opening details;
- successful job creation;
- completing a weekly goal.

Animations should be quick and subtle.

Do not require animation libraries if unnecessary.

## 16.7 Completion feedback

When a user completes a task, use positive but restrained feedback.

Examples:

```text
Nice — one less thing to carry.
```

or simply:

```text
✓ Done
```

Avoid:

- loud confetti after every click;
- XP systems;
- levels;
- artificial streak pressure;
- guilt-inducing messages.

## 16.8 Rejections

Job rejection must not be visually framed as user failure.

When archiving a rejected job, use neutral language:

```text
Application archived
```

Optionally:

```text
Keep notes for future applications.
```

Never show:

```text
FAILED
```

---

# 17. Empty States

Empty states should make the product feel welcoming.

Examples:

## Current Job

```text
Nothing urgent here 🎓
Add the work that currently needs your attention.
```

## Job Search

```text
Your next opportunity starts here 🚀
Save an interesting role or paste a job advert.
```

## Learning

```text
What would make the next application easier? 🌱
Add a skill, project, course, or practice goal.
```

---

# 18. Navigation

Desktop:

```text
Sidebar or compact top navigation

Dashboard
Current Job
Job Search
Learning
```

Mobile:

Use a compact mobile navigation pattern.

The app must remain functional on mobile, although desktop is the primary development target.

Do not create a separate mobile product.

---

# 19. Suggested MVP Routes

Route names may vary depending on framework.

Conceptually:

```text
/
    Dashboard

/work
    Current Job board

/jobs
    Job Search board

/learning
    Learning board

/settings
    Minimal settings
```

Optional:

```text
/archive
```

If archive functionality is simple enough, it may instead live inside `/jobs`.

---

# 20. Settings

Keep settings minimal.

MVP settings:

```text
Weekly available hours
Optional display name
```

Possible future settings:

```text
theme
default priorities
AI provider
API key handling
```

Do not overbuild settings.

---

# 21. Search and Filtering

For the first polished MVP, provide basic filtering.

Useful filters:

```text
Priority
Deadline
Tags
Status
```

Job-specific optional filters:

```text
Company
Fit
```

A full-text search feature is optional.

Do not implement complex query builders.

---

# 22. Workload Calculation

The weekly workload feature should use intentionally transparent logic.

## Input

For each card:

```text
plannedThisWeek
estimatedHours
```

## Calculation

```text
plannedHours =
SUM(estimatedHours)
FOR cards WHERE plannedThisWeek == true
```

Breakdown:

```text
currentJobHours
jobSearchHours
learningHours
```

## Display

Example:

```text
This week
16h / 20h planned

🎓 Current Job   8h
🚀 Job Search    5h
🌱 Learning      3h
```

If some planned cards have no estimate:

```text
16h planned + 2 unestimated tasks
```

Do not silently count missing estimates as zero without indicating that some work is unestimated.

---

# 23. Focus Today Algorithm

Do not use AI for this in MVP.

Implement deterministic ranking.

Suggested conceptual score:

```text
OVERDUE             +100
DUE_TODAY            +80
DUE_WITHIN_2_DAYS    +60

URGENT_PRIORITY      +50
HIGH_PRIORITY        +30
MEDIUM_PRIORITY      +15

IN_PROGRESS          +20
PLANNED_THIS_WEEK    +10
```

Then sort by score.

Tie-breakers:

```text
earliest deadline
highest priority
oldest creation date
```

Try to avoid showing three cards from the same area if comparably important cards exist in other areas.

This diversity rule can be simple.

Example:

```text
Pick highest-ranked card.
Then prefer a different area for card 2 if its score is close.
Then repeat for card 3.
```

Do not overengineer this.

---

# 24. Suggested Data Relationships

Conceptual structure:

```text
User
 │
 ├── Cards
 │    ├── Current Job cards
 │    ├── Job Search cards
 │    └── Learning cards
 │
 ├── JobDetails
 │
 └── Preferences
```

Relationships:

```text
Card 1 ---- 0..1 JobDetails

Job Card * ---- * Learning Card
```

If the chosen database makes many-to-many relations cumbersome, use a simple linking structure.

Example:

```text
JobLearningLink
├── jobCardId
└── learningCardId
```

---

# 25. Persistence Requirements

The final portfolio-quality version should persist data between sessions.

The exact persistence technology will depend on course constraints.

Implementation should separate:

```text
UI
domain logic
persistence layer
```

Do not tightly couple business rules to one database library if avoidable.

For early prototyping, local storage or an in-memory repository is acceptable.

For the final version, use the persistence mechanism required or permitted by the course.

---

# 26. Authentication

Authentication is **not inherently required by the product concept** because the first user is the developer.

If the course requires authentication, implement it.

If not required, it may be postponed.

Do not spend half the project building account management unless necessary.

---

# 27. Technical Architecture Guidance

The stack is intentionally undecided.

Regardless of framework, preserve these conceptual layers:

```text
Presentation
    components
    views
    interactions

Application / domain
    card creation
    status transitions
    workload calculations
    focus ranking
    job-learning relationships

Persistence
    card repository
    job-details repository
    preferences repository

AI integration
    job advert extraction
```

The AI feature must be isolated from the core task-management functionality.

If AI is offline, the app must still work.

---

# 28. Suggested Domain Types

Equivalent types should exist regardless of language.

```text
Area =
    CURRENT_JOB
    JOB_SEARCH
    LEARNING
```

```text
Priority =
    LOW
    MEDIUM
    HIGH
    URGENT
```

Example statuses:

```text
CurrentJobStatus =
    BACKLOG
    THIS_WEEK
    IN_PROGRESS
    WAITING
    DONE
```

```text
JobStatus =
    INTERESTING
    PREPARING
    APPLIED
    INTERVIEW
    OFFER
```

```text
LearningStatus =
    IDEAS
    PLANNED
    LEARNING
    PRACTISING
    DONE
```

Job outcome:

```text
JobOutcome =
    ACTIVE
    REJECTED
    WITHDRAWN
    ACCEPTED
    DECLINED
```

---

# 29. Validation Rules

Keep validation forgiving.

## Base card

Required:

```text
title
area
status
```

Optional:

```text
description
deadline
estimatedHours
priority
tags
subtasks
```

Suggested constraints:

```text
title: 1–200 characters
estimatedHours: >= 0
```

## Job

Recommended but not strictly mandatory:

```text
company
role
```

At minimum, one useful identifier should exist.

Examples:

```text
company + role
```

or a descriptive title.

Do not make salary, location, deadline, or contact mandatory.

---

# 30. Important User Flows

## 30.1 Add academic task

```text
Current Job
→ Add card
→ Enter "Finish rebuttal"
→ Save
→ Card appears in Backlog
```

Optional enrichment:

```text
Priority: Urgent
Deadline: Friday
Estimated time: 3h
Planned this week: Yes
```

## 30.2 Add learning task

```text
Learning
→ Add card
→ "System design course"
→ Planned
→ Estimate 4h
→ Link to Anthropic application
```

## 30.3 Add job manually

```text
Job Search
→ Add job
→ Create manually
→ Company
→ Role
→ URL
→ Deadline
→ Priority / fit
→ Save
→ Appears under Interesting
```

## 30.4 Add job using AI

```text
Job Search
→ Add job
→ Paste job advert
→ Paste text
→ Generate job card
→ Review extracted fields
→ Correct anything necessary
→ Save
→ Appears under Interesting
```

## 30.5 Advance application

```text
Drag:
Interesting
→ Preparing
→ Applied
→ Interview
→ Offer
```

## 30.6 Reject / withdraw application

```text
Open job card
→ Archive
→ Choose:
   Rejected
   Withdrawn
→ Preserve notes
→ Remove from active board
```

## 30.7 Weekly planning

```text
Set weekly capacity: 15h

Mark cards:
Finish paper       5h
Anthropic app      3h
System design      4h
Review paper       2h

Dashboard:
14h / 15h planned
```

---

# 31. Seed Data for Development

Use realistic development fixtures.

## Current Job

```text
Finish conference slides
Priority: HIGH
Deadline: Friday
Estimate: 3h
Status: THIS_WEEK
```

```text
Review journal paper
Priority: MEDIUM
Estimate: 2h
Status: BACKLOG
```

```text
Run final experiment
Priority: HIGH
Estimate: 4h
Status: IN_PROGRESS
```

## Job Search

```text
Anthropic
Research Engineer
Fit: DREAM
Status: INTERVIEW
Interview: Tuesday
Estimate: 3h
```

```text
DeepMind
Research Scientist
Fit: HIGH
Status: PREPARING
Estimate: 2h
```

```text
AI Startup
ML Engineer
Fit: MEDIUM
Status: INTERESTING
```

## Learning

```text
System Design
Status: LEARNING
Estimate: 3h
Linked jobs:
- Anthropic
- DeepMind
```

```text
LeetCode Arrays
Status: PRACTISING
Estimate: 1h
```

```text
Portfolio Project
Status: PLANNED
Estimate: 4h
```

---

# 32. MVP Scope

The MVP is complete when the following work reliably.

## Required

### Unified Dashboard

- three vertical area columns;
- compact active-card summaries;
- weekly workload indicator;
- Focus Today section.

### Current Job Board

- full Kanban;
- add/edit/delete cards;
- drag between statuses.

### Job Search Board

- specialised job cards;
- application stages;
- structured job details;
- rejection/withdrawal archive.

### Learning Board

- full Kanban;
- learning cards;
- optional links to jobs.

### Shared Cards

- priority;
- deadline;
- estimate;
- tags;
- description;
- subtasks;
- planned-this-week flag.

### Persistence

- data survives page refresh / session according to selected course architecture.

### AI

- paste job advert;
- extract job information;
- editable preview;
- save as job card;
- graceful fallback when unavailable.

### Visual quality

- cute / warm visual language;
- responsive layout;
- polished enough for screenshots and portfolio demonstration.

---

# 33. Explicit Non-Goals for MVP

Do **not** implement these unless specifically requested later:

- Gmail integration;
- automatic email parsing;
- calendar integration;
- automatic interview event creation;
- browser extension;
- scraping job sites;
- LinkedIn integration;
- CV generation;
- automatic cover-letter generation;
- AI career coach chat;
- AI daily planner;
- advanced recommendation system;
- application success prediction;
- salary analytics;
- networking CRM;
- multi-user collaboration;
- employer accounts;
- recruiter functionality;
- mobile native applications;
- push notifications;
- complex reminders;
- detailed time tracking;
- Pomodoro timer;
- project dependencies;
- Gantt charts;
- generic team project-management tools;
- XP;
- levels;
- elaborate achievements;
- social leaderboards.

Avoid feature creep.

---

# 34. Future Features

These ideas may be considered only after the MVP is stable.

## AI skill-gap extraction

Given a job advert:

```text
Required skill: distributed systems
Current learning plan: no matching item
```

Suggest:

```text
+ Add "Distributed systems fundamentals" to Learning
```

## User profile

Store:

```text
skills
research background
preferred industries
preferred locations
CV
```

Then compare job adverts against this profile.

## Application analytics

Examples:

```text
Applications sent
Interviews
Offers
Interview conversion rate
Applications by month
```

Analytics should remain supportive, not demoralising.

## Weekly review

Example:

```text
This week:
4 academic tasks completed
2 applications submitted
5h spent learning
1 interview reached
```

## Gentle planning assistance

Eventually:

```text
You have 6h available.
Suggested split:
2h application
2h interview preparation
2h current-job deadline
```

This is future scope, not MVP.

---

# 35. Accessibility

Cute design must not reduce usability.

Requirements:

- sufficient text contrast;
- visible keyboard focus;
- buttons must have text or accessible labels;
- do not rely exclusively on colour to indicate priority/status;
- drag-and-drop should ideally have an accessible fallback;
- sensible touch target sizes;
- readable font size;
- form controls must have labels.

---

# 36. Responsive Behaviour

## Desktop

Primary experience.

Show:

```text
three dashboard columns side by side
full-width Kanban boards
detail drawer
```

## Tablet

Columns may shrink or horizontally scroll where necessary.

## Mobile

Dashboard columns may stack vertically:

```text
Current Job
Job Search
Learning
```

Kanban boards may use horizontal scrolling.

Usability is more important than reproducing the desktop layout exactly.

---

# 37. Error States

Handle errors visibly and calmly.

Examples:

## Persistence failure

```text
Couldn't save that change.
Your card is still open — please try again.
```

## AI failure

```text
I couldn't reliably extract this advert.
You can retry or create the job manually.
```

## Missing job URL

Do nothing special.

URL is optional.

## Invalid estimated hours

Show inline validation.

Avoid generic:

```text
Something went wrong.
```

when a more specific error is available.

---

# 38. Loading States

Use lightweight loading feedback.

Examples:

- skeleton cards;
- subtle spinner;
- disabled Generate button while AI extraction is running.

Do not freeze the entire app for a small operation.

---

# 39. Destructive Actions

Deleting or archiving important data should require reasonable protection.

For example:

```text
Delete card?
This cannot be undone.
```

Archiving a rejected job should not require excessive confirmation because it is a routine workflow.

---

# 40. Portfolio Presentation Requirements

The final project should be easy to demonstrate.

A reviewer should understand the concept within approximately 30 seconds.

The demo should clearly show:

1. unified dashboard;
2. three competing career areas;
3. job application pipeline;
4. workload planning;
5. link between jobs and learning;
6. AI job-advert ingestion;
7. polished visual design.

The README should eventually explain the product as:

> A career-pivot Kanban for academics moving into industry, combining current work, job applications, and skill development in one focused workspace.

---

# 41. Recommended Development Order

Follow this order unless the chosen course stack creates a strong reason not to.

## Phase 1 — Static UI

Build:

- shell;
- navigation;
- dashboard;
- three boards;
- cards;
- visual design.

Use seed data.

Goal:

> The entire product should already be visually understandable before backend complexity is added.

## Phase 2 — Core card interactions

Implement:

- add;
- edit;
- delete;
- status changes;
- drag and drop;
- priorities;
- deadlines;
- estimates;
- tags;
- weekly planning flag.

## Phase 3 — Persistence

Connect the selected persistence layer.

Verify:

- reload;
- create;
- edit;
- delete;
- reorder/status changes.

## Phase 4 — Specialised jobs

Implement:

- JobDetails;
- job form;
- interview date;
- application deadline;
- fit;
- archive;
- outcome.

## Phase 5 — Learning-job relationships

Implement:

```text
job ↔ learning
```

Display linked jobs on learning cards/details.

Display relevant learning items on job details.

## Phase 6 — Dashboard intelligence

Implement:

- weekly capacity;
- workload breakdown;
- Focus Today deterministic ranking.

## Phase 7 — AI advert ingestion

Implement:

- paste advert;
- extraction;
- preview;
- correction;
- card creation;
- fallback.

## Phase 8 — Polish

Improve:

- empty states;
- responsive behaviour;
- accessibility;
- animations;
- loading;
- error states;
- visual consistency.

## Phase 9 — Portfolio preparation

Create:

- polished README;
- screenshots;
- demo seed data;
- short architecture explanation;
- feature summary.

---

# 42. Definition of Done

The project is MVP-complete when a new user can perform this scenario without developer intervention:

1. Open the app.
2. See the unified three-column dashboard.
3. Add an academic task.
4. Add estimated effort and deadline.
5. Add a learning goal.
6. Paste a job advert.
7. Review AI-extracted job data.
8. Save the job.
9. Move the job from Interesting to Preparing.
10. Link a learning card to the job.
11. Mark several cards for this week.
12. Set weekly available hours.
13. See total planned workload.
14. See three Focus Today recommendations.
15. Move an academic task to Done.
16. Move a job to Applied.
17. Archive a rejected job.
18. Reload the application.
19. Confirm that the data remains correct.
20. Use the application comfortably on a normal laptop screen.

Additionally:

- there are no obvious broken layouts;
- empty states exist;
- AI failure does not break the app;
- the application looks intentionally designed rather than like default framework components.

---

# 43. Agent Operating Rules

The coding agent working on this repository must treat this document as the product source of truth.

## 43.1 Do not invent product scope

Do not add major features simply because they are common in productivity applications.

Before adding anything substantial, check whether it is:

- required by this specification;
- necessary for a required feature;
- explicitly requested by the developer.

If not, omit it.

## 43.2 Prefer the simplest complete implementation

Do not build abstractions for hypothetical future SaaS scale.

This is initially:

```text
one-user-first
portfolio-quality
course-constrained
MVP
```

Code quality matters, but unnecessary architecture does not.

## 43.3 Preserve domain terminology

Use:

```text
NextLane
Current Job
Job Search
Learning / Pivot
```

The product is always called **NextLane** — never "the Kanban app", "Career Pivot Kanban", or a placeholder name.

Avoid silently renaming the product into generic concepts such as:

```text
Workspace A
Workspace B
Projects
Tickets
Issues
```

## 43.4 Preserve the unified dashboard

Do not turn the app into three disconnected pages.

The dashboard is a core product feature.

## 43.5 Preserve visual personality

Do not default to a grey enterprise admin dashboard.

The interface should remain:

```text
warm
cute
calm
modern
professional
```

## 43.6 AI is optional to core operation

Never make basic task creation dependent on an LLM request.

## 43.7 Avoid premature authentication work

Only prioritise authentication when:

- the course requires it; or
- persistence architecture requires it; or
- the developer explicitly asks for it.

## 43.8 Make reasonable implementation decisions

For low-level implementation details not covered here, choose sensible defaults and continue.

Examples:

- component naming;
- file structure;
- exact spacing;
- exact database indexes;
- utility functions.

Do not stop development for trivial questions.

## 43.9 Escalate only genuine product ambiguities

Ask for guidance when a decision would materially change:

- user experience;
- scope;
- architecture;
- data ownership;
- privacy;
- core workflows.

## 43.10 Update this specification deliberately

If the product direction changes, edit this document.

Do not allow the implementation and specification to silently diverge.

---

# 44. Short Product Summary for Agent Context

When context is limited, use this condensed description:

> **NextLane** is a responsive, cute-but-professional web Kanban for academics moving into industry. The product has three connected areas: Current Job, Job Search, and Learning/Pivot. The main dashboard shows three vertical columns plus weekly workload and a deterministic Focus Today section. Each area has a full Kanban. Job Search has specialised application data and stages: Interesting → Preparing → Applied → Interview → Offer, with rejected/withdrawn jobs archived. Learning cards can link to job cards. Shared cards support priority, deadline, estimated hours, tags, subtasks, and a planned-this-week flag. Users can optionally set weekly available hours and compare them with planned estimated effort. The only required AI feature is pasting a job advert and extracting an editable structured job card. NextLane must remain fully usable without AI. Keep the MVP focused, visually warm, motivating, and portfolio-quality. Do not add generic productivity features without explicit instruction.

---

# 45. Final Product Test

At every significant implementation decision, ask:

> **Does this make it easier for an academic to balance their current job, job search, and preparation for an industry pivot?**

If the answer is no, the feature probably does not belong in the MVP.
