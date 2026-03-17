import { useState } from 'react'
import type { FormEvent } from 'react'
import { API_BASE_URL, askQuestion, uploadDocument } from './lib/api'
import type { SourceItem } from './types/api'

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<SourceItem[]>([])

  const [uploadStatus, setUploadStatus] = useState('')
  const [askStatus, setAskStatus] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [askError, setAskError] = useState('')

  const [isUploading, setIsUploading] = useState(false)
  const [isAsking, setIsAsking] = useState(false)

  const onUpload = async (event: FormEvent) => {
    event.preventDefault()

    if (!selectedFile) {
      setUploadError('먼저 업로드할 PDF 파일을 선택해주세요.')
      return
    }

    setUploadError('')
    setUploadStatus('')
    setIsUploading(true)

    try {
      const result = await uploadDocument(selectedFile)
      setUploadStatus(result.message)
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : '업로드 중 오류가 발생했습니다.')
    } finally {
      setIsUploading(false)
    }
  }

  const onAsk = async (event: FormEvent) => {
    event.preventDefault()

    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) {
      setAskError('질문을 입력해주세요.')
      return
    }

    setAskError('')
    setAskStatus('')
    setIsAsking(true)

    try {
      const result = await askQuestion({ question: trimmedQuestion })
      setAnswer(result.answer)
      setSources(result.sources)
      setAskStatus('답변을 생성했습니다.')
    } catch (error) {
      setAskError(error instanceof Error ? error.message : '질문 처리 중 오류가 발생했습니다.')
      setAnswer('')
      setSources([])
    } finally {
      setIsAsking(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-900 sm:px-6 lg:px-10">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="rounded-2xl bg-gradient-to-r from-teal-600 to-cyan-700 px-6 py-8 text-white shadow-lg">
          <p className="text-sm font-medium text-cyan-100">DocPilot-RAG</p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
            문서 업로드 기반 AI 질의응답 MVP
          </h1>
          <p className="mt-2 text-sm text-cyan-100 sm:text-base">API Base URL: {API_BASE_URL}</p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">1) 문서 업로드</h2>
            <p className="mt-1 text-sm text-slate-600">PDF 파일을 선택하고 서버로 전송합니다.</p>

            <form className="mt-4 space-y-4" onSubmit={onUpload}>
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-cyan-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-cyan-700"
                disabled={isUploading}
              />
              <button
                type="submit"
                disabled={isUploading}
                className="inline-flex w-full items-center justify-center rounded-lg bg-cyan-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {isUploading ? '업로드 중...' : '업로드'}
              </button>
            </form>

            {uploadStatus && (
              <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{uploadStatus}</p>
            )}
            {uploadError && (
              <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{uploadError}</p>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">2) 질문 입력</h2>
            <p className="mt-1 text-sm text-slate-600">업로드한 문서를 기반으로 질문을 보냅니다.</p>

            <form className="mt-4 space-y-4" onSubmit={onAsk}>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="예: 이 문서의 핵심 내용을 5줄로 요약해줘."
                rows={5}
                disabled={isAsking}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-cyan-700 focus:outline-none"
              />
              <button
                type="submit"
                disabled={isAsking}
                className="inline-flex w-full items-center justify-center rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
              >
                {isAsking ? '질문 처리 중...' : '질문하기'}
              </button>
            </form>

            {askStatus && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{askStatus}</p>}
            {askError && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{askError}</p>}
          </section>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">3) 답변 및 출처</h2>
          <p className="mt-1 text-sm text-slate-600">RAG 응답과 근거 문맥을 함께 확인합니다.</p>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-slate-700">답변</h3>
            {answer ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{answer}</p>
            ) : (
              <p className="mt-2 text-sm text-slate-500">아직 생성된 답변이 없습니다.</p>
            )}
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-700">출처</h3>
            {sources.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">근거 없음: 아직 출처 데이터가 없거나 검색되지 않았습니다.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {sources.map((source, index) => (
                  <li key={`${source.title ?? 'source'}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-medium text-slate-500">
                      {source.title ?? 'Untitled Source'}
                      {typeof source.page === 'number' ? ` · p.${source.page}` : ''}
                    </p>
                    <p className="mt-1 text-sm text-slate-700">{source.snippet}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}

export default App
