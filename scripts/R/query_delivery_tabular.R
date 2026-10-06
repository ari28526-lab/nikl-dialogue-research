# Arguments: dataset root, output JSON, separate Arrow library.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) == 3)
.libPaths(c(args[[3]], .libPaths()))
root <- args[[1]]
final <- jsonlite::read_json(file.path(root, "FINAL.json"), simplifyVector=FALSE)
results <- lapply(final$receipts, function(item) {
  recpath <- file.path(root, item$path)
  rec <- jsonlite::read_json(recpath, simplifyVector=FALSE)
  e <- rec$source
  id_options <- intersect(c("utt_id", "word_id", "source_file", "speaker_id"), unlist(e$columns))
  idcol <- if (length(id_options)) id_options[[1]] else ""
  typed <- vapply(e$typed_fields, function(x) x[[1]], character(1))
  candidates <- intersect(c("duration_seconds", "utterance_start", "start", "source_start_seconds", "begin_seconds"), typed)
  timecol <- if(length(candidates)) candidates[[1]] else ""
  rows <- 0; missing <- 0; nonnegative <- 0; keys <- character()
  cols <- c("_delivery_source_row_index", if(nzchar(idcol)) idcol, if(nzchar(timecol)) paste0("_delivery_typed_",timecol))
  for (output in rec$outputs) {
    x <- as.data.frame(arrow::read_parquet(file.path(dirname(recpath), output$path), col_select=tidyselect::all_of(cols)))
    rows <- rows+nrow(x)
    if(nzchar(timecol)) {
      t <- x[[paste0("_delivery_typed_",timecol)]]
      missing <- missing+sum(is.na(t)); nonnegative <- nonnegative+sum(t>=0, na.rm=TRUE)
    }
    if(length(keys)<20 && nrow(x)) {
      selected <- seq_len(min(nrow(x),20-length(keys)))
      keys <- c(keys,paste0(as.character(x[["_delivery_source_row_index"]][selected]),"|",if(nzchar(idcol)) x[[idcol]][selected] else ""))
    }
  }
  list(partition=e$partition,rows=rows,coordinate_column=timecol,missing_coordinates=missing,
       nonnegative_coordinates=nonnegative,first_keys=unname(keys))
})
jsonlite::write_json(results,args[[2]],auto_unbox=TRUE,pretty=TRUE)
