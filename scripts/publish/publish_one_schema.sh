

proj=$1
pushd $proj
ver=`python ../get_schema_version.py $proj`
echo $ver
esgvoc use "$proj@latest"
esgvoc schema $proj -o schema.json

if [ ! -d $ver ] ; then
    mkdir $ver
    mv schema.json $ver
    git add $ver
else
    res=`diff schema.json | wc -l`
    if [ $res ] ; then
	echo  "Schemas differ for $project/$ver"
    else
       echo  "Matching schemas $project/$ver"
    fi
fi
popd
