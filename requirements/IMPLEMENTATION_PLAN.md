# CharacterVerse AI

## Claude Implementation Plan --- iOS, Android & Backend

**Product:** CharacterVerse AI\
**Platforms:** iOS (SwiftUI), Android (Kotlin + Jetpack Compose),
Backend (Python/FastAPI)\
**Product principle:** Create, mix, and animate original 3D characters
only. No licensed franchise characters, copied character designs, paid
character packs, or assets whose commercial-use rights are unclear.

------------------------------------------------------------------------

# 1. Product vision

CharacterVerse AI is a mobile-first creative studio where users can:

1.  Create original 3D heroes, villains, cartoon characters, fantasy
    creatures, robots, and aliens.
2.  Mix original characters to produce new hybrid characters with
    combined visual traits, abilities, and personalities.
3.  Generate short stories and storyboards featuring their characters.
4.  Place characters in reusable 3D environments and animate them with
    reusable motion clips.
5.  Add dialogue, text-to-speech voices, sound effects, and royalty-free
    or properly licensed music.
6.  Render and export short videos for personal use and sharing.

The product must not depend on famous entertainment characters or their
protected names, logos, costumes, distinctive silhouettes, signature
props, or recognizable designs.

## 1.1 Product pillars

-   **Create:** Design and save original characters.
-   **Mix:** Combine compatible traits, powers, styles, and
    personalities.
-   **Animate:** Turn characters and stories into short 3D videos.
-   **Share:** Export MP4 videos and share them outside the app.

## 1.2 Target users

-   Hobbyist creators and animation fans.
-   Families and casual storytellers.
-   Social-video creators.
-   Users learning character design and storytelling.

## 1.3 MVP scope

The first release should prioritize a reliable, affordable, repeatable
3D workflow rather than promising unrestricted text-to-3D movie
generation.

**MVP includes:** - Original character templates and procedural
customization. - Character profile, save, duplicate, and edit. -
AI-assisted character descriptions and fusion recipes. - A constrained
character mixer using approved traits and compatible rigged models. -
Story and storyboard generation. - A library of reusable animation
clips. - A small set of original environments. - Timeline/scene
sequencing with simple transitions. - Text-to-speech dialogue using a
provider or local engine whose terms permit the intended use. - Backend
video rendering and MP4 export.

**Not in MVP:** - Arbitrary high-quality text-to-3D mesh generation. -
Realistic human likeness generation. - User-uploaded copyrighted
character models. - Open-ended marketplace for third-party character
assets. - Long-form movie production. - Real-time multiplayer editing. -
Voice cloning of real people.

------------------------------------------------------------------------

# 2. Legal, licensing, and content guardrails

These are product requirements, not optional polish.

## 2.1 Original-IP-only policy

-   Do not include Marvel, DC, Disney, Pixar, anime-franchise,
    game-franchise, movie-franchise, or other licensed characters unless
    a future written licence is obtained.
-   Do not use franchise names, logos, character names, signature
    costumes, distinctive props, or marketing language that implies
    affiliation.
-   Do not instruct an image, text, or 3D model to imitate a named
    artist, studio, franchise, or specific protected character.
-   Do not create a renamed near-copy of a recognizable character. A
    different name alone does not make a design original.
-   All built-in characters, meshes, textures, rigs, animations,
    environments, sound effects, and music must be created by the team
    or have documented rights for the intended commercial use.

## 2.2 Model and asset licence registry

Maintain a version-controlled `ASSET_AND_MODEL_LICENSES.md` and a
backend registry containing:

-   Asset/model identifier and version.
-   Creator/source and acquisition date.
-   Licence name and URL or bundled licence text.
-   Commercial-use permission.
-   Attribution requirements.
-   Redistribution and derivative-work permissions.
-   Restrictions, model card, and intended usage.
-   Review status and reviewer.
-   SHA-256 hash for the exact downloaded artifact where practical.

Do not ship an asset or model until its licence has been reviewed. "Open
source", "free download", and "free for research" do not automatically
mean commercial use is allowed.

## 2.3 User content and moderation

-   Provide clear terms explaining that users must have rights to
    uploaded material.
-   Block or flag prompts that request named protected characters,
    franchise logos, or direct imitations.
-   Use a policy classifier plus deterministic deny lists and human
    review for appeals; do not rely on a deny list alone.
-   Give users a report/takedown workflow.
-   Keep audit records for generated assets and moderation decisions.
-   Do not promise that AI output is legally unique or that users
    automatically own all rights in every jurisdiction. Obtain legal
    review of terms, privacy, and ownership language before launch.

------------------------------------------------------------------------

# 3. User journeys

## 3.1 Create a character

1.  User taps **Create Character**.
2.  Chooses a category: Hero, Villain, Cartoon, Fantasy, Robot, Alien,
    or Creature.
3.  Chooses a base body/template and body proportions.
4.  Customizes palette, materials, clothing modules, accessories, face,
    and optional powers.
5.  Optionally enters a text description.
6.  AI converts the description into a validated structured character
    recipe.
7.  App previews the character in a 3D viewer.
8.  User saves the character to **My Universe**.

## 3.2 Mix characters

1.  User selects two or three characters they own or are permitted to
    use.
2.  Selects what to mix: appearance, powers, personality, or all.
3.  AI generates a fusion recipe from approved traits.
4.  Backend validates compatibility and applies weighted parameters to
    an approved base rig/model.
5.  App previews the result.
6.  User adjusts the mix sliders and saves a new character, retaining
    links to source character IDs.

## 3.3 Create an animated short

1.  User selects one to four characters.
2.  Selects a story template or enters a prompt.
3.  AI returns a structured script and storyboard.
4.  User reviews and edits scenes, dialogue, and character actions.
5.  App sends a render job to the backend.
6.  Backend assembles a 3D scene, applies animation clips, audio, camera
    movements, and transitions.
7.  User sees job progress and a preview when complete.
8.  User exports or shares the MP4.

------------------------------------------------------------------------

# 4. Application information architecture

Use a consistent product experience on both mobile platforms.

## 4.1 Main navigation

1.  **Discover** --- original character categories, templates, featured
    creations, tutorials.
2.  **Create** --- character builder and AI character generation.
3.  **Mixer** --- combine saved characters.
4.  **Studio** --- story, storyboard, scene editor, and render queue.
5.  **My Universe** --- saved characters, projects, videos, and drafts.

## 4.2 Screens

### Onboarding and account

-   Welcome and product policy.
-   Sign in / create account.
-   Guest mode with local drafts (optional MVP).
-   Terms, privacy, content policy, and age-appropriate experience.
-   Permission prompts only when needed.

### Discover

-   Category grid.
-   Search and filters.
-   Character template detail.
-   Featured original characters.
-   New-user tutorial.

### Character Library

-   Character cards with thumbnail, name, category, and modified date.
-   Search, sort, filter.
-   Create, duplicate, archive, delete.
-   Character detail with 3D preview and metadata.

### Character Creator

-   Category and base template selection.
-   3D viewport.
-   Body and proportion controls.
-   Face and expression controls.
-   Outfit/accessory selection.
-   Color/material editor.
-   Powers and effects.
-   AI description prompt.
-   Save and version history.

### Character Mixer

-   Select source characters.
-   Mix dimensions: visual, powers, personality, voice profile.
-   Trait contribution sliders.
-   AI fusion suggestions.
-   Compatibility warnings.
-   Preview, regenerate, undo, save as new character.

### Story Creator

-   Prompt input.
-   Genre, tone, audience, duration, and language.
-   Character selection.
-   Story outline.
-   Script and dialogue editor.
-   Safety and originality feedback.

### Storyboard

-   Scene cards.
-   Scene duration.
-   Location/environment.
-   Characters in scene.
-   Action and camera direction.
-   Dialogue and audio.
-   Reorder, duplicate, add, delete.

### Animation Studio

-   3D scene preview.
-   Character placement and scale.
-   Animation clip selection.
-   Timeline and clip trimming.
-   Camera presets.
-   Lighting presets.
-   Background/environment selection.
-   Dialogue and audio tracks.
-   Render settings.

### Render Queue

-   Queued, processing, completed, failed.
-   Progress and estimated stage (do not invent a precise completion
    time).
-   Retry failed job.
-   Cancel queued job.
-   Preview and download/export.

### My Universe

-   Characters.
-   Projects.
-   Rendered videos.
-   Favorites.
-   Storage usage.
-   Delete/export account data.

### Settings

-   Account and privacy.
-   Content preferences.
-   Data export and deletion.
-   Notifications.
-   Help, report content, and legal information.

------------------------------------------------------------------------

# 5. Technical architecture

## 5.1 High-level system

``` text
iOS App (SwiftUI)                 Android App (Compose)
       |                                  |
       +------------ HTTPS API -----------+
                          |
                   API Gateway / FastAPI
                          |
       +------------------+-------------------+
       |                  |                   |
  Auth & Users       Character Service    Project Service
       |                  |                   |
       +------------------+-------------------+
                          |
                  PostgreSQL Database
                          |
                   Job Queue (Redis)
                          |
                Background Worker Pool
                          |
       +------------------+-------------------+
       |                  |                   |
  AI Orchestrator    3D Scene Builder     Audio Pipeline
       |                  |                   |
  LLM / classifiers  Blender / Godot      TTS / FFmpeg
       |                  |                   |
       +------------------+-------------------+
                          |
                 Object Storage (S3 API)
                          |
                Signed upload/download URLs
```

## 5.2 Recommended technology choices

  -----------------------------------------------------------------------
  Area                    Recommendation          Notes
  ----------------------- ----------------------- -----------------------
  iOS                     SwiftUI, Swift 6        Native app, structured
                                                  concurrency

  Android                 Kotlin, Jetpack Compose Native app, coroutines
                                                  and Flow

  3D mobile preview       SceneKit/RealityKit     Select one
                          evaluation on iOS;      cross-platform asset
                          Filament or Unity       format and validate
                          evaluation on Android   parity

  3D asset format         glTF 2.0 / GLB          Shared model
                                                  interchange format;
                                                  test rig and animation
                                                  support

  Backend                 Python 3 + FastAPI      Typed REST API

  Database                PostgreSQL              Users, characters,
                                                  projects, jobs

  Queue                   Redis + Celery,         Background rendering
                          Dramatiq, or RQ         and AI tasks

  3D generation/rendering Blender in worker       Headless scene assembly
                          containers              and rendering

  Real-time engine        Godot or Unity          Evaluate if interactive
  alternative                                     3D editing becomes
                                                  central

  AI orchestration        Provider-neutral Python Swap local and hosted
                          adapters                models

  File storage            S3-compatible object    Models, textures,
                          storage                 audio, renders

  Video assembly          FFmpeg                  Muxing, transitions,
                                                  audio, MP4

  Authentication          OIDC-compatible         Verify provider costs
                          provider or Firebase    and terms
                          Auth                    

  Observability           OpenTelemetry +         Logs, traces,
                          Sentry-compatible       crash/error reporting
                          service                 

  CI/CD                   GitHub Actions          Separate iOS, Android,
                                                  backend pipelines
  -----------------------------------------------------------------------

**Architecture decision:** Do not embed a full game engine in both apps
for the MVP unless the interactive editor requires it. Use native mobile
UI for workflows, a lightweight 3D viewer for previews, and Blender
workers for final video rendering. Run a technical spike to confirm
identical GLB assets, materials, skeletons, and animation clips render
acceptably on both platforms.

## 5.3 Backend services

Start as a modular monolith with clear modules. Split into microservices
only when scale or team boundaries justify it.

-   `auth`: identity, sessions, account deletion.
-   `users`: profiles and preferences.
-   `characters`: character metadata, recipes, versions, ownership.
-   `assets`: approved templates, models, textures, animation clips,
    licences.
-   `mixer`: fusion recipe generation and compatibility validation.
-   `stories`: script and storyboard generation.
-   `projects`: scenes, timeline, drafts, project versions.
-   `render`: job creation, queueing, progress, cancellation, retries.
-   `media`: signed uploads, downloads, thumbnails, transcoding.
-   `moderation`: prompt checks, upload checks, reports, takedowns.
-   `billing`: reserved for a later release; do not make paid generation
    a requirement for MVP.

------------------------------------------------------------------------

# 6. Character system and 3D pipeline

## 6.1 MVP character strategy

Do not attempt unrestricted AI-generated 3D mesh creation in the first
release. It is expensive, inconsistent, difficult to rig, and hard to
keep visually consistent across scenes.

Instead, build an original, licence-cleared library of modular, rigged
base characters:

-   Humanoid base models with varied proportions.
-   Cartoon animal base models.
-   Robot and creature base models.
-   Modular outfits, armor, hair, accessories, and props.
-   Original materials and texture palettes.
-   Standardized skeletons and animation clips.

The AI creates a **Character Recipe** that selects and configures
approved components. The recipe is applied deterministically by the
character assembly service.

## 6.2 Character Recipe

Example logical schema:

``` json
{
  "schemaVersion": 1,
  "name": "Voltwood Guardian",
  "category": "hero",
  "baseModelId": "humanoid_base_01",
  "style": "stylized_cinematic",
  "proportions": {
    "height": 1.08,
    "shoulderWidth": 1.12,
    "headScale": 1.0
  },
  "palette": {
    "primary": "#245A75",
    "secondary": "#4A8C63",
    "accent": "#D7E7A1"
  },
  "modules": [
    "original_armor_shoulders_02",
    "leaf_cape_01",
    "energy_bracers_03"
  ],
  "powers": ["electricity", "plant_growth"],
  "personalityTraits": ["protective", "curious", "calm"],
  "voiceProfileId": "voice_fictional_warm_01",
  "assetManifestVersion": "1.0"
}
```

All IDs must refer to approved assets in the registry. The backend must
reject unknown or unapproved assets.

## 6.3 Fusion engine

The first version is a controlled trait mixer, not arbitrary mesh
merging.

Inputs: - Source character IDs. - User-selected mix dimensions. - Trait
contribution weights. - Optional natural-language intent.

Processing: 1. Load source recipes and verify ownership/permissions. 2.
Extract compatible traits. 3. Ask the LLM for a structured fusion
proposal. 4. Validate against a JSON schema and allowed vocabulary. 5.
Resolve compatible base model and modules. 6. Normalize weights and
resolve conflicts deterministically. 7. Generate the new character
recipe. 8. Assemble a preview GLB. 9. Save the result as a new character
with source lineage.

Example conflict rules: - Incompatible body rigs: select a compatible
base template; do not blend skeletons. - Conflicting powers: allow both
only if the effects are supported by the target rig. - Too many
accessories: apply a deterministic priority and show omitted modules. -
Missing assets: return a clear validation error and suggest
alternatives.

## 6.4 3D asset pipeline

1.  Create or commission original models.
2.  Review asset licence and provenance.
3.  Model in Blender.
4.  Retopologize and create LODs.
5.  UV unwrap and create optimized textures.
6.  Rig to the agreed skeleton standard.
7.  Create animation clips.
8.  Export GLB/glTF.
9.  Run automated validation for missing textures, invalid skeletons,
    polygon budget, file size, and animation names.
10. Generate thumbnails and preview files.
11. Publish an immutable asset version to object storage and the asset
    registry.

## 6.5 Animation library

Create reusable clips before building complex generative animation:

-   Idle, walk, run, jump.
-   Wave, point, clap, laugh.
-   Talk/listen.
-   Dance loops.
-   Fly/hover.
-   Basic action/fight choreography.
-   Hit reaction, fall, get-up, victory.
-   Creature-specific movement.

All clips must be original or properly licensed for commercial use. Use
a shared rig standard where practical.

------------------------------------------------------------------------

# 7. AI services and generation workflow

## 7.1 AI provider abstraction

Define interfaces so the product is not locked to one vendor:

-   `TextGenerationProvider`
-   `ImageGenerationProvider`
-   `SpeechGenerationProvider`
-   `ContentModerationProvider`
-   `EmbeddingProvider` (optional)

Each adapter must expose model name/version, licence or terms URL, cost
metadata where applicable, latency, and availability.

Support local inference where feasible. Hosted APIs may be optional
adapters, not a mandatory dependency. Do not assume a model is
commercially usable until its exact licence and terms are reviewed.

## 7.2 Character prompt-to-recipe flow

``` text
User description
    -> prompt moderation
    -> LLM structured recipe generation
    -> JSON schema validation
    -> asset registry validation
    -> compatibility resolver
    -> deterministic character assembly
    -> preview GLB + thumbnail
    -> user approval and save
```

The model should return structured data, not arbitrary executable code
or raw Blender scripts.

## 7.3 Story and storyboard flow

The LLM returns a structured document containing:

-   Title and logline.
-   Synopsis.
-   Characters and roles.
-   Scene list.
-   Scene duration.
-   Location ID.
-   Character positions.
-   Action IDs from the approved animation library.
-   Dialogue lines.
-   Camera preset IDs.
-   Sound-effect IDs.
-   Music cue IDs.

The app displays the storyboard for user review before rendering.

## 7.4 Text-to-speech and audio

-   Use fictional, non-impersonating voice profiles.
-   Do not clone a real person's voice without explicit rights and
    consent.
-   Maintain a registry of voice provider/model terms.
-   Use original or commercial-use-cleared sound effects and music.
-   Let users mute, replace, or remove audio.
-   Store audio tracks separately until final muxing.

## 7.5 AI cost controls

-   Default to reusable assets and animation clips.
-   Cache identical character previews by recipe hash.
-   Cache generated story drafts by project version where appropriate.
-   Set maximum scene count, duration, resolution, and retry limits.
-   Use low-resolution draft renders before final rendering.
-   Allow users to cancel jobs.
-   Record compute time and provider usage per job.
-   Add configurable quotas and rate limits.
-   Keep expensive hosted video-generation APIs out of the MVP critical
    path.

------------------------------------------------------------------------

# 8. Video rendering architecture

## 8.1 Rendering pipeline

``` text
Approved storyboard
    -> scene validation
    -> fetch GLB assets and animation clips
    -> create Blender scene
    -> place characters and environments
    -> apply actions and camera presets
    -> render scene frames
    -> render/prepare dialogue and audio
    -> FFmpeg combine scenes and audio
    -> encode MP4 (H.264)
    -> create thumbnail and preview
    -> upload output
    -> mark job complete
```

## 8.2 MVP rendering targets

-   Draft preview: 480p or 720p.
-   Final export: 720p initially; 1080p after performance validation.
-   Aspect ratios: 16:9 and 9:16 initially.
-   Duration presets: 15, 30, and 60 seconds.
-   Frame rate: 24 or 30 FPS; choose one default and test rendering
    cost.
-   Output: MP4/H.264 with AAC audio.
-   Render progress: queued, preparing, rendering scenes, composing
    audio/video, uploading, completed, failed.

Do not promise instant rendering. Rendering time depends on scene
complexity, hardware, and queue depth.

## 8.3 Render job reliability

-   Every job has a unique idempotency key.
-   Use durable job state in PostgreSQL.
-   Queue messages may be delivered more than once; workers must be
    idempotent.
-   Retry transient failures with bounded exponential backoff.
-   Store logs and failure codes.
-   Clean up temporary files after a retention period.
-   Support cancellation where safe.
-   Use signed URLs for media access.
-   Never expose object-storage credentials to mobile clients.

------------------------------------------------------------------------

# 9. Data model

Use PostgreSQL with UUID primary keys, timestamps, soft deletion where
needed, and explicit ownership.

## 9.1 Core tables

### users

-   `id`
-   `auth_provider_subject`
-   `email`
-   `display_name`
-   `created_at`
-   `updated_at`
-   `deleted_at`

### characters

-   `id`
-   `owner_user_id`
-   `name`
-   `description`
-   `category`
-   `style`
-   `recipe_json`
-   `preview_asset_id`
-   `thumbnail_asset_id`
-   `visibility` (private/public only if public sharing is later
    enabled)
-   `created_at`
-   `updated_at`
-   `deleted_at`

### character_lineage

-   `id`
-   `character_id`
-   `source_character_id`
-   `contribution_weight`
-   `mix_dimension`

### asset_registry

-   `id`
-   `asset_type`
-   `asset_version`
-   `storage_key`
-   `format`
-   `licence_id`
-   `commercial_use_approved`
-   `provenance`
-   `sha256`
-   `created_at`

### licences

-   `id`
-   `name`
-   `licence_url`
-   `terms_snapshot_key`
-   `commercial_use`
-   `attribution_required`
-   `review_status`
-   `reviewed_at`
-   `reviewer`

### projects

-   `id`
-   `owner_user_id`
-   `title`
-   `description`
-   `status`
-   `settings_json`
-   `created_at`
-   `updated_at`

### scenes

-   `id`
-   `project_id`
-   `sequence_number`
-   `duration_ms`
-   `environment_asset_id`
-   `camera_preset_id`
-   `scene_json`

### render_jobs

-   `id`
-   `project_id`
-   `owner_user_id`
-   `status`
-   `progress_stage`
-   `progress_percent`
-   `settings_json`
-   `output_asset_id`
-   `error_code`
-   `created_at`
-   `started_at`
-   `completed_at`

### media_assets

-   `id`
-   `owner_user_id`
-   `asset_type`
-   `storage_key`
-   `mime_type`
-   `file_size`
-   `duration_ms`
-   `sha256`
-   `created_at`
-   `expires_at`

### moderation_events

-   `id`
-   `user_id`
-   `content_type`
-   `content_id`
-   `decision`
-   `reason_code`
-   `policy_version`
-   `created_at`

## 9.2 Data rules

-   Validate all JSON against versioned schemas.
-   Never trust a client-supplied asset ID without checking the
    registry.
-   Enforce user ownership in every read/write query.
-   Use migrations and seed data.
-   Keep model and asset licence records immutable or versioned.
-   Provide data export and deletion workflows.

------------------------------------------------------------------------

# 10. Backend API outline

Use REST with OpenAPI documentation. Use WebSocket or Server-Sent Events
for job progress only if polling is insufficient for the first release.

## Authentication

-   `POST /v1/auth/session` --- exchange/validate provider token if
    required.
-   `GET /v1/me`
-   `DELETE /v1/me`

## Assets

-   `GET /v1/assets?type=character-template`
-   `GET /v1/assets/{assetId}`
-   `GET /v1/assets/{assetId}/preview-url`

## Characters

-   `GET /v1/characters`
-   `POST /v1/characters`
-   `GET /v1/characters/{characterId}`
-   `PATCH /v1/characters/{characterId}`
-   `DELETE /v1/characters/{characterId}`
-   `POST /v1/characters/generate-recipe`
-   `POST /v1/characters/{characterId}/preview`

## Mixer

-   `POST /v1/mixes/preview`
-   `POST /v1/mixes`
-   `GET /v1/mixes/{mixId}`

## Stories and projects

-   `POST /v1/stories/generate`
-   `POST /v1/projects`
-   `GET /v1/projects`
-   `GET /v1/projects/{projectId}`
-   `PATCH /v1/projects/{projectId}`
-   `POST /v1/projects/{projectId}/storyboard`
-   `PATCH /v1/projects/{projectId}/scenes/{sceneId}`

## Rendering

-   `POST /v1/projects/{projectId}/renders`
-   `GET /v1/renders/{jobId}`
-   `POST /v1/renders/{jobId}/cancel`
-   `GET /v1/renders/{jobId}/download-url`

## Uploads and moderation

-   `POST /v1/uploads/presign`
-   `POST /v1/moderation/check`
-   `POST /v1/reports`

All endpoints require authentication except explicitly public health
checks and public catalogue endpoints. Apply request validation, rate
limiting, ownership checks, and audit logging.

------------------------------------------------------------------------

# 11. iOS implementation plan

## 11.1 Architecture

Use SwiftUI with feature-based modules and MVVM or a unidirectional
state architecture. Keep networking, persistence, and rendering-preview
concerns out of Views.

Suggested structure:

``` text
CharacterVerse/
  App/
    CharacterVerseApp.swift
    AppRouter.swift
    AppEnvironment.swift
  Core/
    Networking/
    Authentication/
    Persistence/
    DesignSystem/
    Analytics/
    Accessibility/
  Features/
    Onboarding/
    Discover/
    CharacterLibrary/
    CharacterCreator/
    CharacterMixer/
    StoryCreator/
    Storyboard/
    AnimationStudio/
    RenderQueue/
    MyUniverse/
    Settings/
  Domain/
    Models/
    UseCases/
    Repositories/
  Data/
    API/
    DTOs/
    RepositoryImplementations/
  ThreeD/
    ModelViewer/
    AssetCache/
    PreviewScene/
  Resources/
  Tests/
```

## 11.2 iOS technical requirements

-   Swift 6 language mode and strict concurrency checking.
-   SwiftUI navigation and reusable design system.
-   `async/await` for API calls.
-   Actors for token refresh, asset cache, and shared mutable state.
-   Repository interfaces for API and local draft storage.
-   Codable DTOs separated from domain models.
-   URLSession with request cancellation and retry policy.
-   Keychain for credentials.
-   SwiftData or Core Data for local drafts and cached metadata.
-   Background upload/download support where appropriate.
-   Lightweight GLB viewer spike; evaluate RealityKit support and a
    compatible alternative before committing.
-   Use `Photos`/share sheet only after user action and permission
    requirements are met.
-   VoiceOver, Dynamic Type, contrast, reduced motion, and localization
    support.

## 11.3 iOS implementation milestones

1.  Create app shell, navigation, theme, and dependency container.
2.  Implement authentication and API client.
3.  Implement Discover and asset catalogue.
4.  Implement character library and local draft support.
5.  Implement 3D preview and asset caching.
6.  Implement Character Creator and recipe validation.
7.  Implement Mixer and fusion preview.
8.  Implement story and storyboard screens.
9.  Implement Animation Studio timeline.
10. Implement render submission, progress, preview, and export.
11. Add accessibility, analytics, crash reporting, and release
    hardening.

------------------------------------------------------------------------

# 12. Android implementation plan

## 12.1 Architecture

Use Kotlin, Jetpack Compose, a feature-oriented structure, repositories,
and ViewModels.

Suggested structure:

``` text
app/
  src/main/java/com/characterverse/
    app/
      CharacterVerseApplication.kt
      MainActivity.kt
      navigation/
    core/
      network/
      auth/
      database/
      datastore/
      design/
      analytics/
      accessibility/
    feature/
      onboarding/
      discover/
      characterlibrary/
      charactercreator/
      charactermixer/
      storycreator/
      storyboard/
      animationstudio/
      renderqueue/
      myuniverse/
      settings/
    domain/
      model/
      repository/
      usecase/
    data/
      api/
      dto/
      repository/
    threed/
      viewer/
      cache/
  src/test/
  src/androidTest/
```

## 12.2 Android technical requirements

-   Kotlin and Jetpack Compose.
-   Coroutines and Flow.
-   ViewModel with immutable UI state.
-   Hilt for dependency injection.
-   Retrofit/OkHttp for API access.
-   Kotlin Serialization or Moshi for DTOs.
-   Room for local drafts and cached metadata.
-   DataStore for preferences.
-   Encrypted storage/Android Keystore for sensitive credentials.
-   WorkManager for deferrable uploads/downloads.
-   GLB viewer spike using Filament or a selected compatible 3D runtime.
-   Android Sharesheet for export sharing.
-   TalkBack, font scaling, contrast, reduced motion, and localization
    support.

## 12.3 Android implementation milestones

1.  Create Compose app shell, navigation, theme, and DI.
2.  Implement authentication and API client.
3.  Implement Discover and asset catalogue.
4.  Implement character library and Room drafts.
5.  Integrate 3D viewer and asset cache.
6.  Implement Character Creator.
7.  Implement Mixer and fusion preview.
8.  Implement story and storyboard flows.
9.  Implement Animation Studio timeline.
10. Implement render jobs, progress, preview, and sharing.
11. Add accessibility, analytics, crash reporting, and release
    hardening.

------------------------------------------------------------------------

# 13. Shared API contracts and cross-platform consistency

-   Maintain OpenAPI as the source of truth for backend endpoints.
-   Generate or validate client DTOs from the API schema where
    practical.
-   Version all character recipes, project documents, and storyboard
    schemas.
-   Use the same GLB assets, animation names, colour tokens, and scene
    JSON on both platforms.
-   Define shared error codes and retry behaviour.
-   Create golden JSON fixtures for both clients.
-   Ensure iOS and Android render the same preview assets and interpret
    the same recipe values.
-   Document platform-specific 3D viewer limitations.

------------------------------------------------------------------------

# 14. Testing strategy

## 14.1 Backend tests

-   Unit tests for recipe validation and fusion compatibility.
-   API tests for authentication, authorization, ownership, and
    validation.
-   Schema compatibility tests.
-   Asset registry licence-gate tests.
-   Prompt moderation tests, including misspellings and indirect
    references.
-   Render worker idempotency and retry tests.
-   Queue failure and worker restart tests.
-   Storage signed URL expiry tests.
-   Data deletion and export tests.
-   Load tests for render submission and job status endpoints.

## 14.2 iOS tests

-   Unit tests for ViewModels/use cases.
-   Repository and API decoding tests.
-   Character recipe validation tests.
-   Mixer state and conflict-resolution tests.
-   UI tests for onboarding, creation, mixing, storyboard, and export.
-   Offline draft and recovery tests.
-   Accessibility audits with VoiceOver and Dynamic Type.
-   Asset download interruption and retry tests.

## 14.3 Android tests

-   Unit tests for ViewModels/use cases.
-   Repository and serialization tests.
-   Character recipe validation tests.
-   Mixer state and conflict-resolution tests.
-   Compose UI tests for critical journeys.
-   Room migration and offline draft tests.
-   WorkManager upload/download tests.
-   Accessibility checks with TalkBack and font scaling.
-   Asset download interruption and retry tests.

## 14.4 3D and render tests

-   Every approved model loads on supported devices.
-   Rig and animation names match the manifest.
-   No missing textures or broken materials.
-   Character identity remains stable between scenes.
-   Camera framing does not cut off important character parts.
-   Audio/video duration and synchronization are correct.
-   MP4 plays on current iOS and Android versions.
-   Render worker handles malformed scene documents safely.

## 14.5 Acceptance criteria

The MVP is ready for beta when:

1.  A user can sign in and create a profile.
2.  A user can browse approved original templates.
3.  A user can create and save a customized character.
4.  A user can mix two compatible characters into a new saved character.
5.  A user can generate and edit a short structured story.
6.  A user can create a storyboard with at least three scenes.
7.  A user can select approved animation clips and environments.
8.  A user can submit a render and see durable job status.
9.  A successful job produces a playable MP4 with audio.
10. A user can export/share the finished video.
11. All shipped assets and models have reviewed licence records.
12. No core workflow requires a paid character pack or paid
    generative-video API.
13. iOS and Android pass the same API contract and core workflow tests.
14. Users can delete their account and associated data according to the
    published retention policy.

------------------------------------------------------------------------

# 15. Security, privacy, and operations

-   Use TLS for all network traffic.
-   Store secrets only in backend secret management, never in mobile
    binaries.
-   Use short-lived signed media URLs.
-   Enforce ownership and authorization server-side.
-   Validate file type, size, duration, and content before processing
    uploads.
-   Scan uploaded files and isolate render workers.
-   Run Blender and FFmpeg workers with least privilege and resource
    limits.
-   Do not execute user-supplied scripts, shaders, or arbitrary scene
    code.
-   Apply rate limits and quotas.
-   Encrypt sensitive data at rest where supported.
-   Define retention periods for uploads, temporary renders, logs, and
    deleted accounts.
-   Provide privacy notices and consent for analytics.
-   Follow applicable privacy requirements, including PIPEDA and
    relevant provincial requirements, with legal review.
-   Add monitoring for API errors, queue depth, worker failures, render
    duration, storage use, and AI-provider usage.

------------------------------------------------------------------------

# 16. Repository and Claude Code workflow

Recommended monorepo:

``` text
characterverse-ai/
  apps/
    ios/
    android/
  backend/
    app/
      api/
      core/
      domain/
      services/
      workers/
      schemas/
      repositories/
    tests/
    migrations/
  shared/
    api-contracts/
    json-schemas/
    design-tokens/
    asset-manifests/
  assets/
    original-character-templates/
    environments/
    animation-clips/
    audio/
  infrastructure/
    docker/
    local-dev/
    deployment/
  docs/
    PRODUCT_REQUIREMENTS.md
    ARCHITECTURE.md
    API_CONTRACTS.md
    ASSET_AND_MODEL_LICENSES.md
    SECURITY_AND_PRIVACY.md
    ADR/
  IMPLEMENTATION_PLAN.md
  README.md
```

## 16.1 Claude Code working rules

Ask Claude to:

-   Read `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, and relevant ADRs
    before coding.
-   Implement one vertical slice at a time.
-   Never invent API fields; update OpenAPI and both clients together.
-   Never add a 3D asset or AI model without a licence record and
    approval.
-   Never use famous franchise character references in prompts, sample
    data, tests, screenshots, or demo videos.
-   Keep secrets out of source control.
-   Add unit tests with each feature.
-   Run formatters, linters, and relevant tests before marking a task
    complete.
-   Update implementation status and decisions in the docs.
-   Keep iOS and Android behaviour aligned.
-   Prefer small pull requests and explicit acceptance criteria.
-   Ask before introducing a paid service or dependency.

## 16.2 Suggested Claude implementation sequence

**Sprint 0 --- Technical validation** - Validate GLB rendering on
representative iOS and Android devices. - Validate Blender headless
rendering in a worker container. - Validate FFmpeg video/audio
composition. - Review candidate model and asset licences. - Produce
architecture decision records.

**Sprint 1 --- Foundation** - Monorepo, CI, backend skeleton,
PostgreSQL, authentication. - iOS and Android app shells. - OpenAPI
contract and shared schemas.

**Sprint 2 --- Original asset catalogue** - Asset registry and licence
gate. - Seed a small set of original rigged templates. - Discover and
character library screens. - 3D preview on both platforms.

**Sprint 3 --- Character Creator** - Recipe schema and validation. -
Modular customization. - Save, edit, duplicate, and version characters.

**Sprint 4 --- Character Mixer** - Fusion recipe generation. -
Compatibility resolver. - Preview assembly. - Save fusion lineage.

**Sprint 5 --- Story and storyboard** - Prompt moderation. - Structured
script generation. - Storyboard editing and persistence.

**Sprint 6 --- Animation Studio** - Environments, character placement,
action clips. - Camera presets and simple timeline. - Scene validation.

**Sprint 7 --- Rendering** - Queue and workers. - Blender scene
generation. - Audio pipeline and FFmpeg composition. - Job progress,
retries, export.

**Sprint 8 --- Beta readiness** - Security and privacy review. -
Accessibility and device testing. - Performance, cost, and reliability
tests. - App Store and Play Store preparation.

------------------------------------------------------------------------

# 17. Deployment and environments

## Local development

-   Docker Compose for FastAPI, PostgreSQL, Redis, and local object
    storage.
-   Mock AI adapters by default.
-   Small sample assets with reviewed licences.
-   Local Blender and FFmpeg worker.
-   Seed accounts and deterministic fixtures.

## Staging

-   Separate database, queue, storage bucket, and credentials.
-   Restricted test users.
-   Render worker limits.
-   Provider usage budgets and alerts.

## Production

-   Managed PostgreSQL.
-   Managed Redis or durable queue.
-   S3-compatible object storage.
-   Autoscaled worker pool with GPU only if a selected model requires
    it.
-   CDN for approved static assets and completed media.
-   Centralized logs, metrics, traces, and alerting.
-   Backups and tested restore procedures.

Do not provision GPU infrastructure until benchmarks demonstrate that
CPU rendering or another lower-cost approach is insufficient for the
target quality and throughput.

------------------------------------------------------------------------

# 18. Risks and mitigation

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Character designs look inconsistent Use rigged templates and
                                      deterministic recipes

  Fusion creates invalid models       Restrict mixing to compatible
                                      modules and traits

  3D rendering is slow                Draft renders, scene limits, queue
                                      workers, caching

  AI costs become unpredictable       Local-first adapters, quotas, usage
                                      accounting

  Model licence is unsuitable         Licence registry and pre-release
                                      review gate

  Users request famous characters     Prompt moderation and clear product
                                      policy

  Mobile 3D parity differs            Early device spike and shared GLB
                                      test suite

  Render jobs fail                    Durable queue, idempotency,
                                      retries, diagnostics

  User uploads are unsafe             File validation, scanning,
                                      isolation, retention policy

  Scope becomes too large             MVP limits and staged release gates
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 19. Definition of done for every feature

A feature is complete only when:

-   User story and acceptance criteria are met.
-   API and schema changes are documented.
-   iOS and Android implementations are aligned where applicable.
-   Unit and integration tests pass.
-   Accessibility is considered and critical paths are tested.
-   Error, loading, empty, and offline states are implemented.
-   Analytics and diagnostics avoid sensitive content.
-   Security and ownership checks are in place.
-   Documentation and implementation status are updated.
-   Any new model, asset, voice, or sound has a reviewed licence record.

------------------------------------------------------------------------

# 20. Final product direction

Build CharacterVerse AI as an **original-character 3D animation
studio**, not a franchise-character remix tool.

The strongest MVP is:

1.  A curated library of original, rigged characters.
2.  A procedural character creator.
3.  An AI-assisted trait and power mixer.
4.  A story and storyboard generator.
5.  A reusable animation and scene editor.
6.  A backend render pipeline that produces short MP4 videos.

This approach is achievable in stages, supports both native mobile
platforms, keeps licensing risk and generation costs under control, and
creates a foundation for more advanced generative 3D features later.

**Claude's first task:** Complete Sprint 0 technical validation and
write ADRs for the mobile 3D viewer, GLB asset standard, Blender
rendering pipeline, AI provider abstraction, and asset licensing
workflow before implementing the full product.
