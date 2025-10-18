package com.example.newsreread

import android.app.Application
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import coil.compose.AsyncImage
import com.example.newsreread.auth.AuthRepository
import com.example.newsreread.auth.AuthState
import com.example.newsreread.auth.AuthViewModel
import com.example.newsreread.data.ApiClient
import com.example.newsreread.data.Article
import com.example.newsreread.data.ArticleRepository
import com.example.newsreread.data.Tag
import com.example.newsreread.ui.ArticleViewModel
import com.example.newsreread.ui.SettingsViewModel
import com.example.newsreread.ui.SettingsViewModelFactory
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val articleViewModel: ArticleViewModel by viewModels { ArticleViewModelFactory(application) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                NewsReReadApp(articleViewModel, intent)
            }
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        // When a new intent is received, update the content with the new intent
        // This is crucial for handling shared URLs when the app is already running.
        if (intent != null) {
            setContent {
                MaterialTheme {
                    NewsReReadApp(articleViewModel, intent)
                }
            }
        }
    }
}

@Composable
fun NewsReReadApp(articleViewModel: ArticleViewModel, intent: Intent) {
    val navController = rememberNavController()
    val authViewModel: AuthViewModel = viewModel()
    val settingsViewModel: SettingsViewModel = viewModel(factory = SettingsViewModelFactory(LocalContext.current.applicationContext as Application))
    val authState by authViewModel.authState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    var showSaveDialog by remember { mutableStateOf<String?>(null) }

    // Effect to handle shared URL from intent
    LaunchedEffect(intent) {
        if (intent.action == Intent.ACTION_SEND && intent.hasExtra("shared_url")) {
            showSaveDialog = intent.getStringExtra("shared_url")
            // Clear the extra to avoid re-triggering the dialog on configuration changes
            intent.removeExtra("shared_url")
        }
    }

    // Effect to show snackbar messages from the ViewModel
    LaunchedEffect(Unit) {
        articleViewModel.message.collectLatest { message ->
            snackbarHostState.showSnackbar(message)
        }
    }

    if (showSaveDialog != null) {
        SaveArticleDialog(
            url = showSaveDialog!!,
            onConfirm = {
                articleViewModel.createArticle(showSaveDialog!!)
                showSaveDialog = null
            },
            onDismiss = { showSaveDialog = null }
        )
    }

    // This effect handles the navigation logic based on the authentication state.
    LaunchedEffect(authState) {
        val currentRoute = navController.currentBackStackEntry?.destination?.route
        if (authState is AuthState.LoggedIn || authState is AuthState.LocalMode) {
            // If login is successful, navigate to the main list screen, clearing the login screen from the back stack.
            if (currentRoute == "login") {
                navController.navigate("list") {
                    popUpTo("login") { inclusive = true }
                }
            }
        } else if (authState is AuthState.LoggedOut) {
            // If the user is logged out, navigate to the login screen, clearing any other screens.
            if (currentRoute != "login") {
                navController.navigate("login") {
                    popUpTo(navController.graph.startDestinationId) { inclusive = true }
                    launchSingleTop = true
                }
            }
        }
    }

    NavHost(navController = navController, startDestination = "list") {
        composable("list") {
            val articles by articleViewModel.articles.collectAsState()
            ArticleListScreen(
                navController = navController,
                articleViewModel = articleViewModel,
                authViewModel = authViewModel,
                articles = articles,
                onFavoriteToggle = { articleViewModel.toggleFavorite(it) },
                snackbarHostState = snackbarHostState
            )
        }
        composable("detail/{articleId}") { backStackEntry ->
            val articleId = backStackEntry.arguments?.getString("articleId")?.toIntOrNull()
            if (articleId != null) {
                LaunchedEffect(articleId) {
                    articleViewModel.loadArticle(articleId)
                }
                val article by articleViewModel.currentArticle.collectAsState()
                article?.let { current ->
                    ArticleDetailScreen(
                        article = current,
                        settingsViewModel = settingsViewModel,
                        onFavoriteToggle = { articleViewModel.toggleFavorite(articleId) },
                        onMemoChange = { memo -> articleViewModel.updateMemo(articleId, memo) },
                        onBack = { navController.popBackStack() }
                    )
                }
            }
        }
        composable("login") { LoginScreen(navController, authViewModel) }
        composable("settings") { SettingsScreen(navController, settingsViewModel) }
    }
}

@Composable
fun SaveArticleDialog(url: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("記事を保存しますか？") },
        text = { Text(url) },
        confirmButton = {
            Button(onClick = onConfirm) {
                Text("保存")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("キャンセル")
            }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterialApi::class)
@Composable
fun ArticleListScreen(
    navController: NavHostController,
    articleViewModel: ArticleViewModel,
    authViewModel: AuthViewModel,
    articles: List<Article>,
    onFavoriteToggle: (Int) -> Unit,
    snackbarHostState: SnackbarHostState
) {
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val authState by authViewModel.authState.collectAsState()
    val isRefreshing by articleViewModel.isRefreshing.collectAsState()
    val pullRefreshState = rememberPullRefreshState(refreshing = isRefreshing, onRefresh = { articleViewModel.refresh() })


    LaunchedEffect(authState) {
        if (authState is AuthState.LoggedIn) {
            articleViewModel.loadArticles()
            articleViewModel.loadTags()
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            AppDrawer(
                articleViewModel = articleViewModel,
                onClose = { scope.launch { drawerState.close() } }
            )
        }
    ) {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbarHostState) },
            topBar = {
                TopAppBar(
                    title = { Text("NewsReRead", fontWeight = FontWeight.Bold) },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Default.Menu, contentDescription = "Menu")
                        }
                    },
                    actions = {
                        var menuExpanded by remember { mutableStateOf(false) }
                        IconButton(onClick = { menuExpanded = true }) {
                            Icon(Icons.Default.AccountCircle, contentDescription = "Account")
                        }
                        DropdownMenu(
                            expanded = menuExpanded,
                            onDismissRequest = { menuExpanded = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("アカウント") },
                                onClick = {
                                    navController.navigate("login")
                                    menuExpanded = false
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("設定") },
                                onClick = {
                                    navController.navigate("settings")
                                    menuExpanded = false
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("ログアウト") },
                                onClick = {
                                    authViewModel.logout()
                                    menuExpanded = false
                                }
                            )
                        }
                    }
                )
            }
        ) { paddingValues ->
            Box(modifier = Modifier.padding(paddingValues).pullRefresh(pullRefreshState)) {
                Column {
                    FilterBar(articleViewModel = articleViewModel)
                    ArticleList(
                        articles = articles,
                        onFavoriteToggle = onFavoriteToggle,
                        onArticleClick = { articleId ->
                            navController.navigate("detail/$articleId")
                        }
                    )
                }
                PullRefreshIndicator(
                    refreshing = isRefreshing,
                    state = pullRefreshState,
                    modifier = Modifier.align(Alignment.TopCenter)
                )
            }
        }
    }
}


@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AppDrawer(articleViewModel: ArticleViewModel, onClose: () -> Unit) {
    val tags by articleViewModel.tags.collectAsState()
    val selectedTagId by articleViewModel.tagId.collectAsState()

    ModalDrawerSheet {
        Column(modifier = Modifier.padding(16.dp)) {
            IconButton(onClick = onClose, modifier = Modifier.align(Alignment.Start)) {
                Icon(Icons.Default.Close, contentDescription = "Close Drawer")
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "タグフィルター",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(bottom = 16.dp)
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                tags.forEach { tag ->
                    Chip(
                        text = tag.name,
                        selected = selectedTagId == tag.id,
                        onClick = { articleViewModel.setFilter(status = articleViewModel.status.value, tagId = if (selectedTagId == tag.id) null else tag.id, isFavorite = null) }
                    )
                }
            }
        }
    }
}

@Composable
fun FilterBar(articleViewModel: ArticleViewModel) {
    val status by articleViewModel.status.collectAsState()
    val isFavorite by articleViewModel.isFavorite.collectAsState()
    val tabs = listOf("unread", "favorite", "archived")

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        shape = MaterialTheme.shapes.medium,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.padding(vertical = 8.dp, horizontal = 16.dp)) {
            TabRow(
                selectedTabIndex = if (isFavorite == true) 1 else status?.let { tabs.indexOf(it) } ?: 0,
                containerColor = Color.Transparent, 
                contentColor = MaterialTheme.colorScheme.primary, 
                divider = {}
            ) {
                tabs.forEachIndexed { _, title ->
                    Tab(
                        selected = (isFavorite == true && title == "favorite") || (status == title),
                        onClick = { 
                            if (title == "favorite") {
                                articleViewModel.setFilter(status = null, tagId = articleViewModel.tagId.value, isFavorite = true)
                            } else {
                                articleViewModel.setFilter(status = title, tagId = articleViewModel.tagId.value, isFavorite = null)
                            }
                        },
                        text = { Text(text = title) }
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            // TODO: 画像にあるスライダーをここに追加
        }
    }
}

@Composable
fun ArticleList(
    articles: List<Article>,
    onFavoriteToggle: (Int) -> Unit,
    onArticleClick: (Int) -> Unit
) {
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        items(articles) { article ->
            ArticleCard(
                article = article,
                onFavoriteToggle = onFavoriteToggle,
                onArticleClick = onArticleClick
            )
        }
    }
}

@Composable
fun ArticleCard(
    article: Article,
    onFavoriteToggle: (Int) -> Unit,
    onArticleClick: (Int) -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onArticleClick(article.id) },
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column {
            Box(modifier = Modifier.height(180.dp)) {
                AsyncImage(
                    model = article.imageUrl,
                    contentDescription = article.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize()
                )
                Box(
                    modifier = Modifier.padding(12.dp).align(Alignment.TopEnd)
                ) {
                    IconButton(onClick = { onFavoriteToggle(article.id) }) {
                        Icon(
                            imageVector = if (article.isFavorite) Icons.Filled.Favorite else Icons.Default.FavoriteBorder,
                            contentDescription = "Favorite",
                            tint = Color.Red,
                            modifier = Modifier
                                .background(Color.Black.copy(alpha = 0.3f), CircleShape)
                                .clip(CircleShape)
                                .padding(8.dp)
                        )
                    }
                }
            }
            Column(modifier = Modifier.padding(16.dp)) {
                Text(article.title ?: "", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                Spacer(modifier = Modifier.height(4.dp))
                Text(article.title ?: "", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(8.dp))
                Text(article.description ?: "", style = MaterialTheme.typography.bodyMedium, maxLines = 3)
                Spacer(modifier = Modifier.height(16.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        article.tags.forEach { tag ->
                            Chip(text = tag.name)
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Visibility, contentDescription = "Views", tint = Color.Gray, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(article.readCount.toString(), color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ArticleDetailScreen(
    article: Article,
    settingsViewModel: SettingsViewModel,
    onFavoriteToggle: (Int) -> Unit,
    onMemoChange: (String) -> Unit,
    onBack: () -> Unit
) {
    val showUrl by settingsViewModel.showUrl.collectAsState()
    val showSummary by settingsViewModel.showSummary.collectAsState()
    val showMemo by settingsViewModel.showMemo.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(article.title ?: "", maxLines = 1) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { onFavoriteToggle(article.id) }) {
                        Icon(
                            imageVector = if (article.isFavorite) Icons.Filled.Favorite else Icons.Default.FavoriteBorder,
                            contentDescription = "Favorite",
                            tint = Color.Red
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Text(article.title ?: "", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            }
            if (showUrl) {
                item {
                    Text("URL: ${article.url}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                }
            }
            item {
                Text("ジャンル", style = MaterialTheme.typography.titleMedium)
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    article.tags.forEach { tag -> Chip(text = tag.name) }
                }
            }
            if (showSummary) {
                item {
                    Text("記事概要", style = MaterialTheme.typography.titleMedium)
                    Text(article.description ?: "", style = MaterialTheme.typography.bodyLarge)
                }
            }
            if (showMemo) {
                item {
                    Text("メモ", style = MaterialTheme.typography.titleMedium)
                    OutlinedTextField(
                        value = article.userMemo ?: "",
                        onValueChange = onMemoChange,
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("この記事に関するメモ...") }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(navController: NavHostController, authViewModel: AuthViewModel) {
    val authState by authViewModel.authState.collectAsState()
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var isRegisterMode by remember { mutableStateOf(false) }
    // The back button is only shown if there is a screen to go back to.
    val canNavigateBack = navController.previousBackStackEntry != null

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (isRegisterMode) "新規登録" else "ログイン") },
                navigationIcon = {
                    if (canNavigateBack) {
                        IconButton(onClick = { navController.navigateUp() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                        }
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            when (val state = authState) {
                is AuthState.LoggedIn, is AuthState.LocalMode, is AuthState.Loading -> {
                    CircularProgressIndicator()
                }
                is AuthState.LoggedOut, is AuthState.Error -> {
                    val title = if (isRegisterMode) "新規登録" else "ログイン"
                    Text(title, style = MaterialTheme.typography.headlineMedium)
                    Spacer(modifier = Modifier.height(24.dp))

                    if (state is AuthState.Error) {
                        Text(state.message, color = MaterialTheme.colorScheme.error)
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    OutlinedTextField(
                        value = username,
                        onValueChange = { username = it },
                        label = { Text("ユーザー名") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    if (isRegisterMode) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedTextField(
                            value = email,
                            onValueChange = { email = it },
                            label = { Text("メールアドレス") },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text("パスワード") },
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        modifier = Modifier.fillMaxWidth()
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(
                        onClick = {
                            if (isRegisterMode) {
                                authViewModel.register(username, email, password)
                            } else {
                                authViewModel.login(username, password)
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(title)
                    }
                    TextButton(onClick = { isRegisterMode = !isRegisterMode }) {
                        Text(if (isRegisterMode) "ログインはこちら" else "新規登録はこちら")
                    }
                    Spacer(modifier = Modifier.height(32.dp))
                    OutlinedButton(onClick = { authViewModel.useLocalMode() }) {
                        Text("ローカルモードで続ける")
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavHostController, settingsViewModel: SettingsViewModel) {
    val showUrl by settingsViewModel.showUrl.collectAsState()
    val showSummary by settingsViewModel.showSummary.collectAsState()
    val showMemo by settingsViewModel.showMemo.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("設定") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("詳細ページの表示設定", style = MaterialTheme.typography.titleMedium)
            SettingSwitch(title = "URLを表示", checked = showUrl, onCheckedChange = { settingsViewModel.setShowUrl(it) })
            SettingSwitch(title = "記事概要を表示", checked = showSummary, onCheckedChange = { settingsViewModel.setShowSummary(it) })
            SettingSwitch(title = "メモ欄を表示", checked = showMemo, onCheckedChange = { settingsViewModel.setShowMemo(it) })
        }
    }
}

@Composable
fun SettingSwitch(title: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(title)
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
fun Chip(text: String, selected: Boolean = false, onClick: () -> Unit = {}) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f),
        modifier = Modifier.clickable(onClick = onClick)
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall
        )
    }
}

// ViewModelFactory to provide the ArticleViewModel
class ArticleViewModelFactory(private val application: Application) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(ArticleViewModel::class.java)) {
            val app = application as NewsReReadApplication
            val authRepository = AuthRepository(app)
            val repository = ArticleRepository(
                ApiClient.apiService,
                app.database.articleDao(),
                authRepository
            )
            @Suppress("UNCHECKED_CAST")
            return ArticleViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}

@Preview(showBackground = true, widthDp = 360, heightDp = 740)
@Composable
fun DefaultPreview() {
    MaterialTheme {
        // The ArticleListScreen preview is currently disabled because it requires an
        // ArticleViewModel, which is not easily available in a preview.
    }
}

@Preview(showBackground = true, widthDp = 360, heightDp = 740)
@Composable
fun DetailPreview() {
    MaterialTheme {
        // Preview is disabled as it requires a SettingsViewModel instance,
        // which is difficult to provide in a @Preview context.
    }
}
