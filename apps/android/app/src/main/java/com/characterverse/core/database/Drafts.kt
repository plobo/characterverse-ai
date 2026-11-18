package com.characterverse.core.database

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

/** Offline character drafts and cached metadata. */
@Entity(tableName = "character_drafts")
data class DraftEntity(
    @PrimaryKey val id: String,
    val recipeJson: String,
    val serverCharacterId: String?,
    val updatedAt: Long,
)

@Entity(tableName = "cached_characters")
data class CachedCharacterEntity(@PrimaryKey val id: String, val json: String, val updatedAt: String)

@Dao
interface DraftDao {
    @Query("SELECT * FROM character_drafts ORDER BY updatedAt DESC") fun observeAll(): Flow<List<DraftEntity>>
    @Query("SELECT * FROM character_drafts ORDER BY updatedAt DESC") suspend fun all(): List<DraftEntity>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(draft: DraftEntity)
    @Query("DELETE FROM character_drafts WHERE id = :id") suspend fun delete(id: String)
    @Query("DELETE FROM character_drafts") suspend fun clear()
}

@Dao
interface CharacterCacheDao {
    @Query("SELECT * FROM cached_characters") suspend fun all(): List<CachedCharacterEntity>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun putAll(items: List<CachedCharacterEntity>)
    @Query("DELETE FROM cached_characters") suspend fun clear()
}

@Database(entities = [DraftEntity::class, CachedCharacterEntity::class], version = 1, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun drafts(): DraftDao
    abstract fun characterCache(): CharacterCacheDao
}
