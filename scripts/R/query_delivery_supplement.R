# root, version, table, exact opaque target ID, output JSON, separate Arrow library.
args <- commandArgs(trailingOnly=TRUE);stopifnot(length(args)==6)
.libPaths(c(args[[6]],.libPaths()))
root <- args[[1]]; wanted_version <- args[[2]]; wanted_table <- args[[3]]; wanted_target <- args[[4]]
final <- jsonlite::read_json(file.path(root,"FINAL.json"),simplifyVector=FALSE);paths <- character()
for(item in final$receipts) {
  rp <- file.path(root,item$path);r <- jsonlite::read_json(rp,simplifyVector=FALSE);e <- r$sources[[1]]
  if(e$version!=wanted_version || e$table!=wanted_table) next
  paths <- c(paths,vapply(r$outputs,function(o)file.path(dirname(rp),o$path),character(1)))
}
stopifnot(length(paths)>0)
dataset <- arrow::open_dataset(paths,format="parquet",partitioning=NULL)
rows <- dataset |> dplyr::filter(analysis_version==wanted_version,table==wanted_table,target_id==wanted_target) |>
  dplyr::select(source_export,source_sha256,source_row_index,item_json) |> dplyr::collect()
stopifnot(nrow(rows)<=50)
result <- list(version=wanted_version,table=wanted_table,matching_rows=nrow(rows),
  source_export=unname(rows$source_export),source_sha256=unname(rows$source_sha256),
  source_row_index=as.numeric(rows$source_row_index),original_item_json=unname(rows$item_json),human_gold=FALSE)
jsonlite::write_json(result,args[[5]],auto_unbox=TRUE,pretty=TRUE,digits=NA,null="null",na="null")
