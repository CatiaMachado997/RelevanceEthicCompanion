import api, { configureApiAuth } from '@/lib/api'

describe('API auth integration', () => {
  beforeEach(() => {
    jest.restoreAllMocks()
    localStorage.clear()
    configureApiAuth({})
  })

  it('adds bearer token header when token is available', async () => {
    localStorage.setItem('access_token', 'abc123')
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', message: 'ok', data: {} }),
      status: 200,
    } as Response)
    ;(globalThis as unknown as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch

    await api.values.create({ type: 'boundary', value: 'test', priority: 1 })

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = (options as RequestInit).headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer abc123')
  })

  it('invokes unauthorized callback on 401 response', async () => {
    const onUnauthorized = jest.fn()
    configureApiAuth({
      getAccessToken: () => 'abc123',
      onUnauthorized,
    })

    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    } as Response)
    ;(globalThis as unknown as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch

    await expect(api.values.create({ type: 'boundary', value: 'test', priority: 1 })).rejects.toThrow(
      'Unauthorized'
    )
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })
})
