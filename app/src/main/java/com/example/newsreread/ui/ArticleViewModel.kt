package com.example.newsreread.ui

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.newsreread.data.Article
import com.example.newsreread.data.ArticleRepository
import com.example.newsreread.data.Tag
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch

class ArticleViewModel(private val repository: ArticleRepository) : ViewModel() {

    private val _articles = MutableStateFlow<List<Article>>(emptyList())
    val articles: StateFlow<List<Article>> = _articles

    private val _currentArticle = MutableStateFlow<Article?>(null)
    val currentArticle: StateFlow<Article?> = _currentArticle

    private val _tags = MutableStateFlow<List<Tag>>(emptyList())
    val tags: StateFlow<List<Tag>> = _tags

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status

    private val _tagId = MutableStateFlow<Int?>(null)
    val tagId: StateFlow<Int?> = _tagId

    private val _isFavorite = MutableStateFlow<Boolean?>(null)
    val isFavorite: StateFlow<Boolean?> = _isFavorite

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing

    private val _message = Channel<String>()
    val message = _message.receiveAsFlow()

    init {
        loadArticles()
        loadTags()
    }

    fun refresh() {
        viewModelScope.launch {
            _isRefreshing.value = true
            try {
                loadArticles()
                loadTags()
            } finally {
                _isRefreshing.value = false
            }
        }
    }

    fun loadArticles() {
        viewModelScope.launch {
            try {
                _articles.value = repository.getArticles(
                    status = _status.value,
                    tagId = _tagId.value,
                    isFavorite = _isFavorite.value
                )
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to load articles", e)
            }
        }
    }

    fun loadTags() {
        viewModelScope.launch {
            try {
                _tags.value = repository.getTags()
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to load tags", e)
            }
        }
    }

    fun setFilter(status: String?, tagId: Int?, isFavorite: Boolean?) {
        _status.value = status
        _tagId.value = tagId
        _isFavorite.value = isFavorite
        loadArticles()
    }

    fun createArticle(url: String) {
        viewModelScope.launch {
            try {
                repository.createArticle(url = url)
                // Refresh the list to show the new article
                loadArticles()
                _message.send("記事を追加しました")
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to create article", e)
            }
        }
    }

    fun loadArticle(id: Int) {
        viewModelScope.launch {
            try {
                _currentArticle.value = repository.getArticle(id)
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to load article", e)
            }
        }
    }

    fun toggleFavorite(id: Int) {
        viewModelScope.launch {
            try {
                val article = _articles.value.find { it.id == id } ?: _currentArticle.value
                if (article != null) {
                    val updatedArticle = repository.updateArticle(id, isFavorite = !article.isFavorite)
                    updateLocalArticleState(updatedArticle)
                }
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to toggle favorite", e)
            }
        }
    }

    fun updateMemo(id: Int, memo: String) {
        viewModelScope.launch {
            try {
                val updatedArticle = repository.updateArticle(id, userMemo = memo)
                updateLocalArticleState(updatedArticle)
            } catch (e: Exception) {
                Log.e("ArticleViewModel", "Failed to update memo", e)
            }
        }
    }

    private fun updateLocalArticleState(updatedArticle: Article) {
        _articles.value = _articles.value.map {
            if (it.id == updatedArticle.id) updatedArticle else it
        }
        if (_currentArticle.value?.id == updatedArticle.id) {
            _currentArticle.value = updatedArticle
        }
    }
}
