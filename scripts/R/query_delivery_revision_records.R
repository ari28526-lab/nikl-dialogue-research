# Shared Python revision/SHA selection; independent R native JSON value checks.
# Args: Arrow Python, package, base tables, revision, corpus, limit,
#       literal text filter (empty = no filter), output JSON.
a <- commandArgs(trailingOnly=TRUE)
if(length(a)!=8L) stop('Expected 8 arguments')
script <- normalizePath(sub('^--file=', '', grep('^--file=', commandArgs(), value=TRUE)[[1]]), winslash='/')
query <- file.path(dirname(script), 'query_delivery_revision_records.py')
if(!file.exists(query)) query <- file.path(dirname(dirname(script)), 'python', 'query_delivery_revision_records.py')
tmp <- tempfile(fileext='.json')
cmd <- c('-B',query,'--package',a[[2]],'--base-tables',a[[3]],'--revision',a[[4]],
         '--corpus',a[[5]],'--limit',a[[6]],'--output',tmp)
if(nzchar(a[[7]])) cmd <- c(cmd,'--contains',a[[7]])
status <- system2(a[[1]],vapply(cmd,shQuote,character(1)))
if(status!=0L) stop('Revision selection failed; no unverified result written')
x <- jsonlite::fromJSON(tmp,simplifyVector=FALSE)
root <- normalizePath(a[[2]],winslash='/',mustWork=TRUE)
cache <- new.env(parent=emptyenv())
ids <- character()
for(row in x$rows) {
  p <- normalizePath(file.path(root,row$source_json),winslash='/',mustWork=TRUE)
  if(!startsWith(tolower(p),paste0(tolower(root),'/'))) stop('Native source escapes package')
  if(!exists(p,envir=cache,inherits=FALSE)) assign(p,jsonlite::fromJSON(p,simplifyVector=FALSE),envir=cache)
  native <- get(p,envir=cache,inherits=FALSE)
  i <- as.integer(row$record_index)+1L
  if(is.na(i)||i<1L||i>length(native$utterances)) stop('Native record index differs')
  value <- native$utterances[[i]]
  payload <- jsonlite::fromJSON(row$payload_json,simplifyVector=FALSE)
  if(!isTRUE(all.equal(value,payload,check.attributes=FALSE))) stop('Native/payload value differs')
  text <- if(a[[5]]=='modu') value$original$form else value$original$text
  for(pair in list(list(value$utterance_id,row$utterance_id),list(text,row$text),
                   list(value$turn_order,row$turn_order),list(value$original$start,row$start),
                   list(value$original$end,row$end),list(value$original$speaker_id,row$speaker_id),
                   list(value$analysis$status,row$analysis_status))) {
    if(!isTRUE(all.equal(pair[[1]],pair[[2]],check.attributes=FALSE))) stop('Projected value differs')
  }
  if(nzchar(a[[7]])&&(is.null(text)||!grepl(a[[7]],text,fixed=TRUE))) stop('Text filter differs')
  ids <- c(ids,paste(row$corpus,row$year,row$discourse_id,row$record_index,sep='|'))
}
if(anyDuplicated(ids)) stop('Duplicate selected record')
x$R_validation <- list(status='selected_native_values_verified',rows=length(x$rows),
  scope='Shared Python revision resolution and SHA checks; independent R selected native payload, IDs, projected values and filter checks. No independent full-corpus scan.')
dir.create(dirname(a[[8]]),recursive=TRUE,showWarnings=FALSE)
jsonlite::write_json(x,a[[8]],auto_unbox=TRUE,pretty=TRUE,digits=NA,null='null',na='null')
unlink(tmp)
