export type SourceItem = {
  title?: string
  page?: number
  snippet: string
}

export type AskRequest = {
  question: string
}

export type AskResponse = {
  answer: string
  sources: SourceItem[]
}

export type UploadResponse = {
  message: string
}
