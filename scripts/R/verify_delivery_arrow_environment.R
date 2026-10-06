.libPaths(c(file.path(getwd(), "work/r_delivery_library"), .libPaths()))
x <- as.data.frame(arrow::read_parquet("work/delivery_arrow_python_probe.parquet"))
expected <- data.frame(id=c("001", "002", "003"), text=c("한글", "", NA_character_), offset=c(0L, 1L, NA_integer_))
stopifnot(identical(x, expected))
receipt <- list(status="bidirectional_environment_probe_passed", checked_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  R_version=as.character(getRversion()), arrow_version=as.character(packageVersion("arrow")),
  Python_probe=jsonlite::read_json("work/delivery_arrow_environment_probe.json", simplifyVector=TRUE),
  R_read_of_Python_probe_passed=TRUE, scope="3 synthetic rows; corpus conversion and corpus query equivalence are not yet verified",
  corpus_conversion_complete=FALSE, delivery_complete=FALSE)
receipt$Python_probe$R_read_of_Python_probe_pending <- FALSE
jsonlite::write_json(receipt, "outputs/reports/bareun32_reanalysis_plan_20260926/DELIVERY_ARROW_ENVIRONMENT.json", pretty=TRUE, auto_unbox=TRUE)
cat("Bidirectional Python/R environment probe passed\n")
