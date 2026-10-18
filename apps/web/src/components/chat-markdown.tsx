import Markdown from "react-markdown";
import styles from "./chat-markdown.module.css";

export function ChatMarkdown({ children }: { children: string }) {
  return (
    <div className={styles.content}>
      <Markdown
        skipHtml
        allowedElements={["p", "strong", "em", "ul", "ol", "li", "code", "pre", "blockquote", "a", "br", "hr"]}
        unwrapDisallowed
        urlTransform={(url) => /^https?:\/\/[^\s\\]+$/i.test(url) ? url : ""}
        components={{ a: ({ href, children }) => href ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span> }}
      >{children}</Markdown>
    </div>
  );
}
