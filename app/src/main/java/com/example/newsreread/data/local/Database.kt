package com.example.newsreread.data.local

import android.content.Context
import androidx.room.*
import com.example.newsreread.data.Action
import com.example.newsreread.data.Article
import com.example.newsreread.data.Question
import com.example.newsreread.data.Tag

@Entity(tableName = "articles")
data class ArticleEntity(
    @PrimaryKey val id: Int,
    val url: String,
    val title: String?,
    val description: String?,
    val imageUrl: String?,
    val status: String,
    val isFavorite: Boolean,
    val priority: String,
    val userMemo: String?,
    val userSummary: String?,
    val readCount: Int,
    val savedAt: String,
    val lastReadAt: String?,
    val repetitionLevel: Int,
    val nextReminderDate: String?
)

@Entity(tableName = "tags")
data class TagEntity(
    @PrimaryKey val id: Int,
    val name: String
)

@Entity(tableName = "questions")
data class QuestionEntity(
    @PrimaryKey val id: Int,
    val articleId: Int,
    val text: String,
    val createdAt: String
)

@Entity(tableName = "actions")
data class ActionEntity(
    @PrimaryKey val id: Int,
    val articleId: Int,
    val text: String,
    val isDone: Boolean,
    val createdAt: String
)

@Entity(tableName = "article_tag_cross_ref", primaryKeys = ["articleId", "tagId"])
data class ArticleTagCrossRef(
    val articleId: Int,
    val tagId: Int
)

data class ArticleWithDetails(
    @Embedded val article: ArticleEntity,
    @Relation(
        parentColumn = "id",
        entityColumn = "id",
        associateBy = Junction(
            value = ArticleTagCrossRef::class,
            parentColumn = "articleId",
            entityColumn = "tagId"
        )
    )
    val tags: List<TagEntity>,
    @Relation(parentColumn = "id", entityColumn = "articleId")
    val questions: List<QuestionEntity>,
    @Relation(parentColumn = "id", entityColumn = "articleId")
    val actions: List<ActionEntity>
)

@Dao
interface ArticleDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertArticles(articles: List<ArticleEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTags(tags: List<TagEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertQuestions(questions: List<QuestionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertActions(actions: List<ActionEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertArticleTagCrossRefs(crossRefs: List<ArticleTagCrossRef>)

    @Transaction
    @Query("SELECT * FROM articles")
    suspend fun getArticlesWithDetails(): List<ArticleWithDetails>

    @Transaction
    suspend fun insertArticlesAndRelations(articles: List<Article>) {
        val articleEntities = articles.map { it.toEntity() }
        val tagEntities = articles.flatMap { it.tags }.distinctBy { it.id }.map { it.toEntity() }
        val questionEntities = articles.flatMap { article -> article.questions.map { it.toEntity(article.id) } }.distinctBy { it.id }
        val actionEntities = articles.flatMap { article -> article.actions.map { it.toEntity(article.id) } }.distinctBy { it.id }
        val crossRefs = articles.flatMap { article ->
            article.tags.map { tag ->
                ArticleTagCrossRef(articleId = article.id, tagId = tag.id)
            }
        }
        insertArticles(articleEntities)
        insertTags(tagEntities)
        insertQuestions(questionEntities)
        insertActions(actionEntities)
        insertArticleTagCrossRefs(crossRefs)
    }
}

fun Article.toEntity() = ArticleEntity(
    id = id,
    url = url,
    title = title,
    description = description,
    imageUrl = imageUrl,
    status = status,
    isFavorite = isFavorite,
    priority = priority,
    userMemo = userMemo,
    userSummary = userSummary,
    readCount = readCount,
    savedAt = savedAt,
    lastReadAt = lastReadAt,
    repetitionLevel = repetitionLevel,
    nextReminderDate = nextReminderDate
)

fun Tag.toEntity() = TagEntity(id = id, name = name)
fun Question.toEntity(articleId: Int) = QuestionEntity(id = id, articleId = articleId, text = text, createdAt = createdAt)
fun Action.toEntity(articleId: Int) = ActionEntity(id = id, articleId = articleId, text = text, isDone = isDone, createdAt = createdAt)

fun ArticleWithDetails.toModel() = Article(
    id = article.id,
    url = article.url,
    title = article.title,
    description = article.description,
    imageUrl = article.imageUrl,
    status = article.status,
    isFavorite = article.isFavorite,
    priority = article.priority,
    userMemo = article.userMemo,
    userSummary = article.userSummary,
    tags = tags.map { it.toModel() },
    questions = questions.map { it.toModel() },
    actions = actions.map { it.toModel() },
    readCount = article.readCount,
    savedAt = article.savedAt,
    lastReadAt = article.lastReadAt,
    repetitionLevel = article.repetitionLevel,
    nextReminderDate = article.nextReminderDate
)

fun TagEntity.toModel() = Tag(id = id, name = name)
fun QuestionEntity.toModel() = Question(id = id, article = articleId, text = text, createdAt = createdAt)
fun ActionEntity.toModel() = Action(id = id, article = articleId, text = text, isDone = isDone, createdAt = createdAt)

@Database(entities = [ArticleEntity::class, TagEntity::class, ArticleTagCrossRef::class, QuestionEntity::class, ActionEntity::class], version = 3, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun articleDao(): ArticleDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "news_reread_database"
                ).fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
