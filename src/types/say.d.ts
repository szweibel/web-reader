declare module 'say' {
  export function speak(
    text: string,
    voice?: string,
    speed?: number,
    callback?: (err: Error | null) => void
  ): void;
}
