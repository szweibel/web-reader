declare module 'say' {
  interface Say {
    speak(
      text: string,
      voice?: string,
      speed?: number,
      callback?: (err: Error | null) => void
    ): void;
    stop(): void;
  }

  const say: Say;
  export default say;
}
