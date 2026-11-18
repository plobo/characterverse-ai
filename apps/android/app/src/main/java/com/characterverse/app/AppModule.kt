package com.characterverse.app

import android.content.Context
import androidx.room.Room
import com.characterverse.BuildConfig
import com.characterverse.core.auth.TokenStore
import com.characterverse.core.database.AppDatabase
import com.characterverse.data.api.ApiService
import com.characterverse.data.repository.RemoteRepository
import com.characterverse.data.repository.RoomDraftRepository
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.repository.*
import com.characterverse.domain.usecase.FusionResolver
import com.characterverse.domain.usecase.PartAssembler
import com.characterverse.domain.usecase.RecipeValidator
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    @Provides @Singleton
    fun catalog(@ApplicationContext context: Context): Catalog = Catalog.fromJson(
        context.assets.open("asset_manifest_v1.json").bufferedReader().readText(),
        context.assets.open("procedural_parts_v1.json").bufferedReader().readText(),
    )

    @Provides fun validator(c: Catalog) = RecipeValidator(c)
    @Provides fun assembler(c: Catalog) = PartAssembler(c)
    @Provides fun fusion(c: Catalog) = FusionResolver(c)

    @Provides @Singleton
    fun okHttp(tokens: TokenStore): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val req = chain.request().newBuilder().header("Accept", "application/json")
            tokens.tokenBlocking()?.let { req.header("Authorization", "Bearer $it") }
            chain.proceed(req.build())
        }
        .build()

    @Provides @Singleton
    fun api(client: OkHttpClient): ApiService = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build().create(ApiService::class.java)

    @Provides @Singleton
    fun database(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, "characterverse.db").build()
}

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    @Binds abstract fun account(r: RemoteRepository): AccountRepository
    @Binds abstract fun characters(r: RemoteRepository): CharacterRepository
    @Binds abstract fun mixes(r: RemoteRepository): MixRepository
    @Binds abstract fun projects(r: RemoteRepository): ProjectRepository
    @Binds abstract fun renders(r: RemoteRepository): RenderRepository
    @Binds abstract fun drafts(r: RoomDraftRepository): DraftRepository
}
