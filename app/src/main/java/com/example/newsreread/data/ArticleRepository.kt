package com.example.newsreread.data

import com.example.newsreread.auth.AuthRepository
import com.example.newsreread.data.local.ArticleDao
import com.example.newsreread.data.local.toModel

class ArticleRepository(
    private val apiService: ApiService,
    private val articleDao: ArticleDao,
    private val authRepository: AuthRepository
) {

    suspend fun getArticles(query: String? = null, status: String? = null, tagId: Int? = null, isFavorite: Boolean? = null): List<Article> {
        return if (authRepository.getAccessToken() != null) {
            val articles = apiService.getArticles(query, status, tagId, isFavorite)
            articleDao.insertArticlesAndRelations(articles)
            articles
        } else {
            articleDao.getArticlesWithDetails().map { it.toModel() }
        }
    }

    suspend fun getTags(): List<Tag> {
        return if (authRepository.getAccessToken() != null) {
            apiService.getTags()
        } else {
            // In local mode, we could fetch tags from the local DB
            emptyList()
        }
    }

    suspend fun createArticle(url: String, tagIds: List<Int>? = null, userMemo: String? = null, status: String? = "unread"): Article {
        val request = CreateArticleRequest(
            url = url,
            tagIds = tagIds,
            userMemo = userMemo,
            status = status
        )
        return apiService.createArticle(request)
    }

    suspend fun getArticle(id: Int): Article {
        return if (authRepository.getAccessToken() != null) {
            apiService.getArticle(id)
        } else {
            // This is a simplification. A full implementation would query the local DB.
            // Returning a dummy article to avoid crashing the app in local mode.
            Article(id, "", "", "", "", "", false, "medium", 0, "", "", "", "", 0, "", emptyList(), emptyList(), emptyList())
        }
    }

    suspend fun updateArticle(id: Int, userMemo: String? = null, status: String? = null, isFavorite: Boolean? = null): Article {
        val request = UpdateArticleRequest(
            userMemo = userMemo,
            status = status,
            isFavorite = isFavorite
        )
        return apiService.updateArticle(id, request)
    }

    suspend fun deleteArticle(id: Int) {
        apiService.deleteArticle(id)
    }

    suspend fun markArticleAsRead(id: Int): Article {
        return apiService.markArticleAsRead(id)
    }

    suspend fun getReminders(): List<Article> {
        return apiService.getReminders()
    }

    suspend fun getRandomArticle(): Article {
        return apiService.getRandomArticle()
    }
}
