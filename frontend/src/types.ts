export type Status = "Active" | "Future" | "Expired" | "Missing";

export interface FieldSpec {
  name: string;
  label: string;
  kind: "text" | "date" | "lookup";
  required: boolean;
  lookup: string | null;
  help: string | null;
  user_managed: boolean;
}

export interface DomainDescriptor {
  key: string;
  label: string;
  uc_target: string | null;
  pk: string;
  fields: FieldSpec[];
  list_columns: string[];
  search_fields: string[];
  filter_fields: string[];
  business_key: string[];
  coverage_dimension: string | null;
}

export interface Me {
  user: string;
  role: string;
  is_admin: boolean;
  roles: string[];
}

export interface ExtraCol {
  name: string;
  label: string;
  help: string | null;
}

export interface ReferenceListMeta {
  key: string;
  label: string;
  note: string | null;
  extra_cols: ExtraCol[];
}

export interface Bootstrap {
  domain: DomainDescriptor;
  lookups: Record<string, string[]>;
  reference_lists: ReferenceListMeta[];
  me: Me;
}

export type Row = Record<string, any> & {
  mapping_id: number;
  status: Status;
  updated_by?: string;
  updated_at?: string;
};

export interface Coverage {
  dimension: string | null;
  all: string[];
  covered: string[];
  gaps: string[];
}

export interface ValidateResult {
  errors: string[];
  coverage: { fills_gap: boolean; dimension: string | null; value: string | null };
}

export interface AuditRow {
  audit_id: number;
  changed_at: string;
  changed_by: string;
  action: string;
  domain_key: string;
  record_pk: string;
  before_json: any;
  after_json: any;
}

export interface ReferenceOption {
  id: number;
  name: string;
  is_active: boolean;
  sort_order: number;
  [k: string]: any;
}

export interface ReferenceDetail {
  key: string;
  label: string;
  note: string | null;
  extra_cols: ExtraCol[];
  options: ReferenceOption[];
}
