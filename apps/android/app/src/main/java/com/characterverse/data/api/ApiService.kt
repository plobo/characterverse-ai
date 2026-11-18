package com.characterverse.data.api

import com.characterverse.data.dto.*
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Retrofit binding of shared/api-contracts/openapi.json (same endpoints as the iOS client). */
interface ApiService {
    @POST("v1/auth/session") suspend fun session(@Body body: SessionRequestDto): SessionResponseDto
    @GET("v1/me") suspend fun me(): UserDto
    @GET("v1/me/usage") suspend fun usage(): UsageDto
    @GET("v1/me/export") suspend fun export(): ExportDto
    @DELETE("v1/me") suspend fun deleteMe(): retrofit2.Response<Unit>

    @GET("v1/characters")
    suspend fun characters(@Query("sort") sort: String = "updated", @Query("includeArchived") includeArchived: Boolean = true,
                           @Query("search") search: String? = null): ItemsDto<CharacterDto>
    @POST("v1/characters") suspend fun createCharacter(@Body body: CreateCharacterDto): CharacterDto
    @PATCH("v1/characters/{id}") suspend fun updateCharacter(@Path("id") id: String, @Body body: UpdateCharacterDto): CharacterDto
    @DELETE("v1/characters/{id}") suspend fun deleteCharacter(@Path("id") id: String): retrofit2.Response<Unit>
    @POST("v1/characters/{id}/duplicate") suspend fun duplicateCharacter(@Path("id") id: String): CharacterDto
    @POST("v1/characters/generate-recipe") suspend fun generateRecipe(@Body body: GenerateRecipeRequestDto): GenerateRecipeResponseDto

    @POST("v1/mixes/preview") suspend fun mixPreview(@Body body: MixRequestDto): MixPreviewDto
    @POST("v1/mixes") suspend fun saveMix(@Body body: MixRequestDto): MixDto

    @POST("v1/stories/generate") suspend fun generateStory(@Body body: GenerateStoryRequestDto): GenerateStoryResponseDto
    @GET("v1/projects") suspend fun projects(): ItemsDto<ProjectDto>
    @POST("v1/projects") suspend fun createProject(@Body body: CreateProjectDto): ProjectDto
    @POST("v1/projects/{id}/storyboard") suspend fun saveStoryboard(@Path("id") id: String, @Body body: StoryboardRequestDto): ProjectDto
    @DELETE("v1/projects/{id}") suspend fun deleteProject(@Path("id") id: String): retrofit2.Response<Unit>

    @GET("v1/renders") suspend fun renders(): ItemsDto<RenderJobDto>
    @POST("v1/projects/{id}/renders")
    suspend fun submitRender(@Path("id") projectId: String, @Header("Idempotency-Key") key: String, @Body body: CreateRenderDto): RenderJobDto
    @GET("v1/renders/{id}") suspend fun render(@Path("id") id: String): RenderJobDto
    @POST("v1/renders/{id}/cancel") suspend fun cancelRender(@Path("id") id: String): RenderJobDto
    @POST("v1/renders/{id}/retry") suspend fun retryRender(@Path("id") id: String): RenderJobDto
    @GET("v1/renders/{id}/download-url") suspend fun downloadUrl(@Path("id") id: String): DownloadUrlDto

    @POST("v1/moderation/check") suspend fun moderationCheck(@Body body: ModerationCheckDto): ModerationDto
    @POST("v1/reports") suspend fun report(@Body body: ReportDto): ReportResponseDto
}
