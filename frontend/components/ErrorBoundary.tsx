'use client'
import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { hasError: boolean }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-4 text-center text-muted-foreground">
          <p className="text-sm">Something went wrong.</p>
          <button onClick={() => this.setState({ hasError: false })}
            className="text-sm underline mt-1">Try again</button>
        </div>
      )
    }
    return this.props.children
  }
}
