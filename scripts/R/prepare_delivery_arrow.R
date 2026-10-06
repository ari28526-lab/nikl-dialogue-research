# Separate delivery-only library. Existing MFA/Python and user R libraries remain unchanged.
delivery_lib <- file.path(getwd(), "work", "r_delivery_library")
dir.create(delivery_lib, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(delivery_lib, .libPaths()))
if (!requireNamespace("arrow", quietly = TRUE)) {
  install.packages("arrow", lib = delivery_lib, repos = "https://cloud.r-project.org", type = "binary")
}
stopifnot(requireNamespace("arrow", quietly = TRUE))
cat("arrow=", as.character(packageVersion("arrow")), "\n", sep = "")
cat("library=", find.package("arrow"), "\n", sep = "")
probe <- data.frame(id = c("001", "002", "003"), text = c("한글", "", NA_character_), offset = c(0L, 1L, NA_integer_))
probe_file <- file.path(getwd(), "work", "delivery_arrow_probe.parquet")
arrow::write_parquet(probe, probe_file)
stopifnot(identical(probe, as.data.frame(arrow::read_parquet(probe_file))))
cat("R Parquet write/read value and missingness check passed\n")
