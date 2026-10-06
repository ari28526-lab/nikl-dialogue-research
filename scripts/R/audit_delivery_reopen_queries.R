# Independent R read: all query paths are relative to the relocated root.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==4L)
.libPaths(c(args[[4]], .libPaths()))
suppressPackageStartupMessages(library(arrow))
suppressPackageStartupMessages(library(jsonlite))
plan <- fromJSON(args[[2]], simplifyVector=FALSE)
stopifnot(identical(plan$schema, 'delivery_reopen_queries.v1'))
results <- lapply(plan$cases, function(cs) {
  stopifnot(!grepl('(^/|\\\\|:|(^|/)\\.\\.(/|$))', cs$path))
  cols <- unlist(cs$columns, use.names=FALSE)
  data <- read_parquet(file.path(args[[1]],cs$path), col_select=all_of(cols), as_data_frame=TRUE)
  stopifnot(nrow(data)==cs$rows)
  for (col in cols) if (inherits(data[[col]],'integer64')) {
    stopifnot(all(is.na(data[[col]]) | abs(as.double(data[[col]])) <= 2^53))
    data[[col]] <- as.double(data[[col]])
  }
  category <- data[[cs$category]]
  kinds <- unique(category)
  counts <- lapply(seq_along(kinds), function(i) {
    key <- kinds[[i]]
    list(value=if (is.na(key)) NULL else key,
         n=if (is.na(key)) sum(is.na(category)) else sum(category==key,na.rm=TRUE))
  })
  selected <- lapply(seq_len(min(cs$sample_rows,nrow(data))),function(i) {
    setNames(lapply(cols,function(k) {
      v <- data[[k]][[i]]
      if (is.na(v) && !is.nan(v)) NULL else if (k %in% unlist(cs$float_columns)) {
        list(ieee754_le_hex=paste(sprintf('%02x',as.integer(writeBin(as.double(v),raw(),size=8,endian='little'))),collapse=''))
      } else v
    }),cols)
  })
  list(id=cs$id, rows=nrow(data), null_counts=as.list(vapply(data,function(x) sum(is.na(x) & !is.nan(x)),integer(1))),
       counts=counts, selected=selected)
})
write_json(list(cases=results),args[[3]],auto_unbox=TRUE,pretty=TRUE,null='null',na='null',digits=NA)
