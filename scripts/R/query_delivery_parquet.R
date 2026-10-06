# Arguments: dataset root, version, output JSON, optional separate Arrow library.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) >= 3)
if (length(args) >= 4) .libPaths(c(args[[4]], .libPaths()))
dataset_root <- args[[1]]; analysis_version <- args[[2]]
paths <- sort(Sys.glob(file.path(dataset_root, paste0("version=", analysis_version), "corpus=modu", "year=*", "table=morphemes", "group-*", "part-*.parquet")))
stopifnot(length(paths) > 0)
columns <- c("_source_csv", "_source_row_index", "utt_id", "token_index", "morph_index", "pos")
counts <- integer(); selected <- character(); total <- 0
for (path in paths) {
  x <- as.data.frame(arrow::read_parquet(path, col_select=tidyselect::all_of(columns)))
  total <- total + nrow(x)
  current <- table(x$pos)
  for (name in names(current)) {
    if (!(name %in% names(counts))) counts[[name]] <- 0
    counts[[name]] <- counts[[name]] + as.numeric(current[[name]])
  }
  if (length(selected) < 50) {
    rows <- head(which(x$pos == "NNG"), 50 - length(selected))
    if (length(rows)) selected <- c(selected, do.call(paste, c(lapply(x[rows, columns[1:5], drop=FALSE], as.character), sep="|")))
  }
}
result <- list(version=analysis_version, pos="NNG", files=length(paths), rows=total,
  counts=as.list(counts[order(names(counts))]), selected_keys=unname(selected), scope="all morphology partitions", human_verified=FALSE)
jsonlite::write_json(result, args[[3]], auto_unbox=TRUE, pretty=TRUE)
