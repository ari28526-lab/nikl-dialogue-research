# root, corpus, discourse ID, utterance ID, radius, output JSON, Arrow library.
# Raw JSON strings retain original native values without R reserializing numbers.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==7)
.libPaths(c(args[[7]],.libPaths()))
root <- args[[1]]; wanted_corpus <- args[[2]]; wanted_discourse <- args[[3]]; wanted_utterance <- args[[4]]
radius <- as.integer(args[[5]])
stopifnot(wanted_corpus %in% c("seoul","modu"),!is.na(radius),radius>=0)
final <- jsonlite::read_json(file.path(root,"FINAL.json"),simplifyVector=FALSE)
paths <- list(documents=character(),records=character())
for(item in final$receipts) {
  rp <- file.path(root,item$path)
  r <- jsonlite::read_json(rp,simplifyVector=FALSE)
  if(r$sources[[1]]$corpus!=wanted_corpus) next
  for(o in r$outputs) paths[[o$table]] <- c(paths[[o$table]],file.path(dirname(rp),o$path))
}
stopifnot(length(paths$documents)>0,length(paths$records)>0)
dataset <- arrow::open_dataset(paths$records,format="parquet",partitioning=NULL)
target <- dataset |>
  dplyr::filter(discourse_id==wanted_discourse,corpus==wanted_corpus,utterance_id==wanted_utterance) |>
  dplyr::select(record_index,source_json) |> dplyr::collect()
stopifnot(nrow(target)==1)
index <- as.numeric(target$record_index[[1]]); wanted_source <- target$source_json[[1]]
lower <- max(0,index-radius); upper <- index+radius
nearby <- dataset |>
  dplyr::filter(discourse_id==wanted_discourse,corpus==wanted_corpus,source_json==wanted_source,record_index>=lower,record_index<=upper) |>
  dplyr::select(utterance_id,turn_order,record_index,text,start,end,analysis_status,payload_json) |>
  dplyr::collect()
nearby <- nearby[order(nearby$record_index),]
docs <- arrow::open_dataset(paths$documents,format="parquet",partitioning=NULL) |>
  dplyr::filter(discourse_id==wanted_discourse,corpus==wanted_corpus,source_json==wanted_source) |>
  dplyr::select(source_sha256,metadata_json) |> dplyr::collect()
stopifnot(nrow(docs)==1)
result <- list(corpus=wanted_corpus,discourse_id=wanted_discourse,target_utterance_id=wanted_utterance,radius=radius,
  source_json=wanted_source,source_sha256=docs$source_sha256[[1]],
  selected_ids=unname(nearby$utterance_id),turn_order=as.numeric(nearby$turn_order),
  original_metadata_json=docs$metadata_json[[1]],original_utterance_json=unname(nearby$payload_json),
  human_verified=FALSE)
jsonlite::write_json(result,args[[6]],auto_unbox=TRUE,pretty=TRUE,digits=NA,null="null",na="null")
