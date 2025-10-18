package com.example.newsreread.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// region Models for GET requests (Receiving data)

@Serializable
data class Article(
    val id: Int,
    val url: String,
    val title: String?,
    val description: String?,
    @SerialName("image_url")
    val imageUrl: String?,
    val status: String,
    @SerialName("is_favorite")
    val isFavorite: Boolean,
    val priority: String = "medium",
    @SerialName("read_count")
    val readCount: Int,
    @SerialName("user_memo")
    val userMemo: String?,
    @SerialName("user_summary")
    val userSummary: String?,
    @SerialName("saved_at")
    val savedAt: String,
    @SerialName("last_read_at")
    val lastReadAt: String?,
    @SerialName("repetition_level")
    val repetitionLevel: Int,
    @SerialName("next_reminder_date")
    val nextReminderDate: String?,
    val tags: List<Tag> = emptyList(),
    val questions: List<Question> = emptyList(),
    val actions: List<Action> = emptyList()
)

@Serializable
data class Tag(
    val id: Int,
    val name: String
)

@Serializable
data class Question(
    val id: Int,
    val article: Int,
    val text: String,
    @SerialName("created_at")
    val createdAt: String
)

@Serializable
data class Action(
    val id: Int,
    val article: Int,
    val text: String,
    @SerialName("is_done")
    val isDone: Boolean,
    @SerialName("created_at")
    val createdAt: String
)

@Serializable
data class User(
    val id: Int,
    val username: String,
    val email: String
)

// endregion

// region Models for POST/PATCH requests (Sending data)

@Serializable
data class CreateArticleRequest(
    val url: String,
    val status: String? = null,
    @SerialName("user_memo")
    val userMemo: String? = null,
    @SerialName("tag_ids")
    val tagIds: List<Int>? = null
)

@Serializable
data class UpdateArticleRequest(
    val status: String? = null,
    @SerialName("is_favorite")
    val isFavorite: Boolean? = null,
    @SerialName("user_memo")
    val userMemo: String? = null
)

// endregion

// region Models for Authentication

@Serializable
data class TokenPair(
    val access: String,
    val refresh: String
)

@Serializable
data class RegisterErrorResponse(
    val username: List<String>? = null,
    val password: List<String>? = null,
    val email: List<String>? = null
)

// endregion
