export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

// Thin, deliberately trivial wrapper — exists only so call sites reach for
// `<TextInput>` alongside `<NumberInput>`/`<Select>` for visual consistency,
// not because plain text inputs needed any real new behavior.
export function TextInput({ className, ...rest }: TextInputProps) {
  return <input type="text" className={['ui-text-input', className].filter(Boolean).join(' ')} {...rest} />
}
