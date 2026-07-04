// E2E 全局类型声明
declare global {
  interface Window {
    __REACT_QUERY_CONFIG__?: {
      staleTime: number
      retry: number | ((failureCount: number, error: Error) => boolean)
    }
  }
}

export {}
