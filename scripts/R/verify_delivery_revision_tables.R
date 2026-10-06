args <- commandArgs(trailingOnly=TRUE)
if(!length(args) %in% c(3L,4L)) stop('Expected CSV, Parquet, result and optional Arrow library paths')
if(length(args)==4L) .libPaths(c(args[4],.libPaths()))
suppressPackageStartupMessages(library(arrow))
suppressPackageStartupMessages(library(jsonlite))
cells <- read.csv(args[1],colClasses='character',check.names=FALSE,na.strings=NULL,fileEncoding='UTF-8')
native <- as.data.frame(read_parquet(args[2]))
if(!identical(names(cells),names(native)) || nrow(cells)!=nrow(native)) stop('Schema or row count differs')
for(i in seq_len(nrow(cells))) for(j in seq_along(cells)) {
  left <- fromJSON(cells[[j]][i],simplifyVector=FALSE)
  right <- native[[j]][i]
  if(length(right)==1L && is.na(right)) right <- NULL
  if(inherits(right,'integer64')) right <- as.numeric(right)
  if(!isTRUE(all.equal(left,right,check.attributes=FALSE))) stop(sprintf('Cell differs: row%d column%s',i,names(cells)[j]))
}
result <- list(status='selected_revision_csv_parquet_equal',rows=nrow(cells),columns=names(cells),
               scope='Explicit selected table only; no full corpus scan',delivery_complete=FALSE)
write_json(result,args[3],pretty=TRUE,auto_unbox=TRUE,null='null')
cat('Selected revision CSV/Parquet R verification passed\n')
