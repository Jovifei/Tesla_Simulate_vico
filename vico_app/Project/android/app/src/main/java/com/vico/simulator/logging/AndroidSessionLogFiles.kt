package com.vico.simulator.logging

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import java.io.File
import java.io.OutputStream
import java.security.MessageDigest

/** Background IO only; app-owned numeric logs, no coordinates, microphone, or network upload. */
object AndroidSessionLogFiles {
    fun apkIdentity(base: String, splits: Array<String>?): String {
        val files = listOf(File(base)) + (splits?.map(::File) ?: emptyList())
        if(files.size==1)return "apk:"+hash(files.single())
        val digest=MessageDigest.getInstance("SHA-256")
        for(file in files.sortedBy{it.name}){
            digest.update(file.name.toByteArray(Charsets.UTF_8));digest.update(0.toByte())
            digest.update(hash(file).toByteArray(Charsets.US_ASCII));digest.update(0.toByte())
        }
        return "apkset:"+digest.digest().joinToString(""){"%02x".format(it)}
    }
    private fun hash(file: File):String {
        val digest=MessageDigest.getInstance("SHA-256");val buffer=ByteArray(64*1024)
        file.inputStream().use { input -> while(true){val n=input.read(buffer);if(n<0)break;digest.update(buffer,0,n)} }
        return digest.digest().joinToString(""){"%02x".format(it)}
    }
    fun latest(root: File):File? = root.listFiles()?.asSequence()
        ?.filter{it.isDirectory&&it.name.matches(Regex("session-[0-9a-fA-F-]{36}"))}
        ?.flatMap{dir->sequenceOf(File(dir,"records.tsv"),File(dir,"records.partial.tsv"))}
        ?.filter{it.isFile}?.maxByOrNull{it.lastModified()}
    fun recordFile(directory:File):File? = File(directory,"records.tsv").takeIf{it.isFile}
        ?: File(directory,"records.partial.tsv").takeIf{it.isFile}
    fun exportName(file:File):String = "vico-test-${file.parentFile?.name ?: "session"}"+
        (if(file.name.contains("partial"))".partial" else "")+".tsv"
    fun copyOwned(root:File,source:File,output:OutputStream){
        require(source.canonicalPath.startsWith(root.canonicalPath+File.separator))
        require(source.name in setOf("records.tsv","records.partial.tsv"))
        source.inputStream().use{it.copyTo(output,64*1024)}
    }
    @androidx.annotation.RequiresApi(android.os.Build.VERSION_CODES.Q)
    fun exportDownloads(context:Context,root:File,source:File):Boolean {
        check(Build.VERSION.SDK_INT>=Build.VERSION_CODES.Q)
        val resolver=context.contentResolver
        val values=ContentValues().apply{
            put(MediaStore.MediaColumns.DISPLAY_NAME,exportName(source));put(MediaStore.MediaColumns.MIME_TYPE,"text/tab-separated-values")
            put(MediaStore.MediaColumns.RELATIVE_PATH,"Download/VicoTests");put(MediaStore.MediaColumns.IS_PENDING,1)
        }
        val uri=resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values) ?: return false
        return try {
            resolver.openOutputStream(uri)?.use{copyOwned(root,source,it)} ?: error("Cannot open export")
            values.clear();values.put(MediaStore.MediaColumns.IS_PENDING,0);check(resolver.update(uri,values,null,null)>0)
            true
        } catch (_:Exception){resolver.delete(uri,null,null);false}
    }
}
