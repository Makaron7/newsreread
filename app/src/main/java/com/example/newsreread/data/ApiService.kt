package com.example.newsreread.data

import android.content.Context
import com.example.newsreread.auth.AuthRepository
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.http.*

interface ApiService {
    // Article endpoints
    @GET("articles/")
    suspend fun getArticles(
        @Query("q") query: String? = null,
        @Query("status") status: String? = null,
        @Query("tag_id") tagId: Int? = null,
        @Query("is_favorite") isFavorite: Boolean? = null
    ): List<Article>

    @POST("articles/")
    suspend fun createArticle(@Body article: CreateArticleRequest): Article

    @GET("articles/{id}/")
    suspend fun getArticle(@Path("id") id: Int): Article

    @PATCH("articles/{id}/")
    suspend fun updateArticle(@Path("id") id: Int, @Body article: UpdateArticleRequest): Article

    @DELETE("articles/{id}/")
    suspend fun deleteArticle(@Path("id") id: Int)

    @POST("articles/{id}/mark_as_read/")
    suspend fun markArticleAsRead(@Path("id") id: Int): Article

    @GET("articles/reminders/")
    suspend fun getReminders(): List<Article>

    @GET("articles/random_pickup/")
    suspend fun getRandomArticle(): Article

    // Tag endpoints
    @GET("tags/")
    suspend fun getTags(): List<Tag>

    @POST("tags/")
    suspend fun createTag(@Body tag: Map<String, String>): Tag

    // Auth endpoints
    @POST("auth/register/")
    suspend fun register(@Body user: Map<String, String>): User

    @POST("auth/token/")
    suspend fun login(@Body credentials: Map<String, String>): TokenPair

    @POST("auth/token/refresh/")
    suspend fun refreshToken(@Body refreshToken: Map<String, String>): TokenPair

    @GET("auth/user/")
    suspend fun getUser(): User
}

object ApiClient {
    private const val BASE_URL = "http://10.0.2.2:8000/api/"

    private val json = Json { ignoreUnknownKeys = true }

    lateinit var apiService: ApiService

    fun initialize(context: Context) {
        val authRepository = AuthRepository(context)
        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(authRepository))
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        apiService = retrofit.create(ApiService::class.java)
    }
}