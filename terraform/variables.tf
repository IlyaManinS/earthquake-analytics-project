#Some defaults will be in the non-commitable file

variable "credentials" {
  description = "Path to GCP service account credentials JSON file"
  type        = string
}

variable "project" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "location" {
  description = "GCP location for multi-regional resources"
  type        = string
  default     = "US" 
}

variable "gcs_bucket_name" {
  description = "Name for the GCS bucket (must be globally unique)"
  type        = string
}

variable "bq_dataset_name" { 
  description = "Name for the BigQuery dataset"
  type        = string
}

variable "gcs_storage_class" {
  description = "Storage class for GCS bucket"
  type        = string
  default     = "STANDARD" 
}