package com.baron.ai

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Base64
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

class MainActivity : Activity() {

    private lateinit var web: WebView
    private val pool = Executors.newFixedThreadPool(12)
    private val live = ConcurrentHashMap<String, HttpURLConnection>()
    @Volatile private var webHandlesBack = false
    private var speech: SpeechRecognizer? = null
    private val FILE_PICK = 9001
    private val MIC_PERM = 9002

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(saved: Bundle?) {
        super.onCreate(saved)

        web = WebView(this).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
                textZoom = 100
                mediaPlaybackRequiresUserGesture = true
            }
            webViewClient = WebViewClient()
            webChromeClient = WebChromeClient()
            setBackgroundColor(0xFF0D0D0D.toInt())
            addJavascriptInterface(Bridge(), "Native")
        }

        setContentView(web)
        web.loadUrl("file:///android_asset/index.html")
    }

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (webHandlesBack) {
            web.evaluateJavascript("window.onAndroidBack && window.onAndroidBack()", null)
        } else {
            super.onBackPressed()
        }
    }

    override fun onDestroy() {
        speech?.destroy()
        live.values.forEach { runCatching { it.disconnect() } }
        pool.shutdownNow()
        super.onDestroy()
    }

    @Deprecated("Use ActivityResult API")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_PICK && resultCode == RESULT_OK) {
            val uris = mutableListOf<Uri>()
            data?.clipData?.let { clip ->
                for (i in 0 until clip.itemCount) uris.add(clip.getItemAt(i).uri)
            } ?: data?.data?.let { uris.add(it) }

            for (uri in uris) {
                pool.execute { readAndEmitFile(uri) }
            }
        }
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(code, perms, results)
        if (code == MIC_PERM && results.isNotEmpty() && results[0] == PackageManager.PERMISSION_GRANTED) {
            startListening()
        } else {
            emit("speech", "error", "Mikrofon izni verilmedi")
        }
    }

    private fun emit(id: String, type: String, payload: String?) {
        val js = "window.__native(" +
                JSONObject.quote(id) + "," +
                JSONObject.quote(type) + "," +
                (if (payload == null) "null" else JSONObject.quote(payload)) + ")"
        web.post { web.evaluateJavascript(js, null) }
    }

    private fun readAndEmitFile(uri: Uri) {
        try {
            val name = uri.lastPathSegment ?: "file"
            val mime = contentResolver.getType(uri) ?: "application/octet-stream"
            val isText = mime.startsWith("text/") ||
                    mime.contains("json") || mime.contains("xml") ||
                    mime.contains("javascript") || mime.contains("csv") ||
                    mime.contains("yaml") || mime.contains("markdown") ||
                    name.matches(Regex(".*\\.(txt|md|py|js|ts|kt|java|c|cpp|h|go|rs|rb|php|css|html|sql|sh|yml|yaml|toml|ini|cfg|log|csv|tsv|json|xml)$", RegexOption.IGNORE_CASE))

            if (isText) {
                val text = contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } ?: ""
                val info = JSONObject().apply {
                    put("name", name)
                    put("mime", mime)
                    put("type", "text")
                    put("content", text)
                    put("size", text.length)
                }
                emit("file", "data", info.toString())
            } else {
                val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: ByteArray(0)
                val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                val info = JSONObject().apply {
                    put("name", name)
                    put("mime", mime)
                    put("type", "binary")
                    put("content", b64)
                    put("size", bytes.size)
                }
                emit("file", "data", info.toString())
            }
        } catch (e: Exception) {
            emit("file", "error", e.message ?: "Dosya okunamadi")
        }
    }

    private fun startListening() {
        if (speech == null) {
            speech = SpeechRecognizer.createSpeechRecognizer(this)
            speech?.setRecognitionListener(object : RecognitionListener {
                override fun onResults(results: Bundle?) {
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        emit("speech", "result", matches[0])
                    }
                    emit("speech", "done", null)
                }
                override fun onPartialResults(partial: Bundle?) {
                    val matches = partial?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        emit("speech", "partial", matches[0])
                    }
                }
                override fun onError(error: Int) {
                    val msg = when (error) {
                        SpeechRecognizer.ERROR_NO_MATCH -> "Ses algilanamadi"
                        SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Ag hatasi"
                        SpeechRecognizer.ERROR_AUDIO -> "Ses kayit hatasi"
                        else -> "Hata: $error"
                    }
                    emit("speech", "error", msg)
                    emit("speech", "done", null)
                }
                override fun onReadyForSpeech(params: Bundle?) { emit("speech", "listening", null) }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        speech?.startListening(intent)
    }

    inner class Bridge {

        @JavascriptInterface
        fun request(id: String, spec: String) {
            pool.execute {
                var conn: HttpURLConnection? = null
                try {
                    val j = JSONObject(spec)
                    val body: String? = if (j.isNull("body")) null else j.getString("body")

                    conn = (URL(j.getString("url")).openConnection() as HttpURLConnection).apply {
                        requestMethod = if (body == null) "GET" else "POST"
                        connectTimeout = 30_000
                        readTimeout = 600_000
                        instanceFollowRedirects = true
                        setRequestProperty("accept", if (body == null) "application/json" else "text/event-stream")
                        setRequestProperty("user-agent", "BaronAI/2.0")
                        val h = j.optJSONObject("headers")
                        h?.keys()?.forEach { k -> setRequestProperty(k, h.getString(k)) }
                        if (body != null) {
                            doOutput = true
                            setChunkedStreamingMode(0)
                        }
                    }
                    live[id] = conn

                    if (body != null) {
                        conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                    }

                    val code = conn.responseCode
                    if (code !in 200..299) {
                        val err = (conn.errorStream ?: conn.inputStream)
                            ?.bufferedReader()?.use { it.readText() } ?: ""
                        emit(id, "error", "HTTP $code · " + err.take(800))
                        return@execute
                    }

                    if (body == null) {
                        val text = conn.inputStream.bufferedReader().use { it.readText() }
                        emit(id, "chunk", text)
                        emit(id, "done", null)
                        return@execute
                    }

                    BufferedReader(InputStreamReader(conn.inputStream, Charsets.UTF_8)).use { r ->
                        while (true) {
                            if (!live.containsKey(id)) return@execute
                            val line = r.readLine() ?: break
                            val t = line.trim()
                            if (t.startsWith("data:")) {
                                emit(id, "chunk", t.substring(5).trim())
                            } else if (t.startsWith("error:") || t.startsWith("{\"error")) {
                                emit(id, "chunk", t)
                            }
                        }
                    }
                    emit(id, "done", null)

                } catch (e: Exception) {
                    if (live.containsKey(id)) {
                        emit(id, "error", e.message ?: e.javaClass.simpleName)
                    }
                } finally {
                    live.remove(id)
                    runCatching { conn?.disconnect() }
                }
            }
        }

        @JavascriptInterface
        fun cancel(id: String) {
            val c = live.remove(id)
            pool.execute { runCatching { c?.disconnect() } }
        }

        @JavascriptInterface
        fun setBack(on: Boolean) {
            webHandlesBack = on
        }

        @JavascriptInterface
        fun pickFile(multiple: Boolean) {
            runOnUiThread {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    if (multiple) putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                }
                startActivityForResult(intent, FILE_PICK)
            }
        }

        @JavascriptInterface
        fun startSpeech() {
            runOnUiThread {
                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO)
                    != PackageManager.PERMISSION_GRANTED) {
                    ActivityCompat.requestPermissions(this@MainActivity,
                        arrayOf(Manifest.permission.RECORD_AUDIO), MIC_PERM)
                } else {
                    startListening()
                }
            }
        }

        @JavascriptInterface
        fun stopSpeech() {
            runOnUiThread { speech?.stopListening() }
        }

        @JavascriptInterface
        fun hasSpeech(): Boolean {
            return SpeechRecognizer.isRecognitionAvailable(this@MainActivity)
        }
    }
}
