import type { ReactNode, SelectHTMLAttributes } from "react";
import { useId } from "react";
import { Button } from "./Button";
import { Search } from "./icons";

export interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
}

/** Labelled form field wrapper (`.field`). */
export function Field({ label, hint, htmlFor, children }: FieldProps) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={htmlFor}>
        {label}
      </label>
      {hint != null ? <span className="field__hint">{hint}</span> : null}
      {children}
    </div>
  );
}

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

/** DSFR-style select (`.select`). */
export function Select({ className, ...rest }: SelectProps) {
  return <select className={["select", className].filter(Boolean).join(" ")} {...rest} />;
}

export interface CheckRowProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  count?: number;
}

/** A checkbox row (`.check-row`) for facets/filters, with an optional trailing count. */
export function CheckRow({ checked, onChange, children, count }: CheckRowProps) {
  return (
    <label className="check-row">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span style={{ flex: 1 }}>{children}</span>
      {count != null ? <span className="fr-xs text-mention tnum">{count}</span> : null}
    </label>
  );
}

export interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
  /** Accessible label for the input + submit button. */
  label: string;
}

/** Search bar (`.searchbar`): a text input + submit button, submitting on Enter. */
export function SearchBar({ value, onChange, onSubmit, placeholder, label }: SearchBarProps) {
  const inputId = useId();
  return (
    <form
      className="searchbar"
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit?.();
      }}
    >
      <label className="sr-only" htmlFor={inputId}>
        {label}
      </label>
      <input
        id={inputId}
        className="input"
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <Button type="submit" aria-label="Lancer la recherche">
        <Search />
      </Button>
    </form>
  );
}
