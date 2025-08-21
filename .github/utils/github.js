import { readdir, readFile } from "node:fs/promises";

async function getReleaseVersion() {
  try {
    return (await readFile("release_version.txt")).toString().trim();
  } catch (err) {
    if (err.code === "ENOENT") {
      // File does not exist
      return null;
    }
    throw err;
  }
}

async function uploadReleaseArtifacts({ github, context }) {
  const tag = await getReleaseVersion();
  if (!tag) {
    console.log("This change did not result in a release.");
    return
  }

  const { owner, repo } = context.repo;

  const files = await readdir("dist");
  const artifacts = files.filter((f) => f.endsWith(".whl") || f.endsWith(".tar.gz"));

  const getRelease = await github.rest.repos.getReleaseByTag({
    owner,
    repo,
    tag,
  });
  const release_id = getRelease.data.id;

  for await (const name of artifacts) {
    const data = await readFile(`dist/${name}`);
    await github.rest.repos.uploadReleaseAsset({
      owner,
      repo,
      release_id,
      name,
      data,
    });
  }
}

async function commentReleaseNotes({ github, context }) {
  let commentBody = "Merging this PR will not result in a release.";

  const versionNumber = await getReleaseVersion();
  if (versionNumber) {
    const releaseNotes = (await readFile("release_notes.txt")).toString().trim();
    commentBody = `Merging this PR will release \`${versionNumber}\` with the following release notes:\n\n${releaseNotes}`;
  }

  // Add an invisible breadcrumb to the comment body so we can find it later
  const bodyBreadcrumb = "<!-- semantic-release-breadcrumb -->\n";
  const issueContext = {
    issue_number: context.issue.number,
    owner: context.repo.owner,
    repo: context.repo.repo,
  };

  const comment = {
    ...issueContext,
    body: `${bodyBreadcrumb}${commentBody}`,
  };

  for await (const { data } of github.paginate.iterator(
    github.rest.issues.listComments, issueContext
  )) {
    for (const {id, body} of data) {
      if (body.startsWith(bodyBreadcrumb)) {
        console.log(`Updating comment ${id}`);
        await github.rest.issues.updateComment({
          comment_id: id,
          ...comment,
        });
        return;
      }
    }
  }

  // Pre-condition: we haven't already commented on this PR
  console.log("Creating comment");
  await github.rest.issues.createComment(comment);
  return;
}

export { uploadReleaseArtifacts, commentReleaseNotes };
