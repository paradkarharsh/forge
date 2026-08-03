export type Brand<Value, Name extends string> = Value & { readonly __brand: Name };
export type RequestId = Brand<string, 'RequestId'>;
export interface ApiError { readonly code: string; readonly message: string; readonly requestId: RequestId; }
